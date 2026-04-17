"""
Audio ingestion pipeline.

1. Validate upload (size + content-type) — fail fast before paying Whisper.
2. Transcribe via Whisper.
3. Call `audio_extraction_agent` with the transcript PLUS the household's
   current values as context, so the model can interpret relative statements
   ("bump my income 10%") and emit `quotes` that reference the transcript.
4. Normalize incoming vs existing values before deciding update-vs-conflict
   (trim whitespace, case-fold free-text, compare numerics as Decimals).
5. Persist the source quote alongside each conflict so the advisor sees
   exactly why the change was proposed.
6. Also persist NEW members and NEW accounts extracted from the transcript,
   and raise conflicts when extracted member/account fields contradict
   existing stored values.
"""
import uuid
from decimal import Decimal, InvalidOperation

import logfire
from fastapi import HTTPException, UploadFile
from openai import AsyncOpenAI

from app.agents.audio_extraction import (
    ExtractedAccount,
    ExtractedHouseholdData,
    ExtractedMember,
    audio_extraction_agent,
    build_extraction_prompt,
)
from app.core import jobs as job_store
from app.core.config import settings
from app.repositories.account_repo import AccountRepository
from app.repositories.household_repo import HouseholdRepository
from app.repositories.member_repo import MemberRepository
from app.schemas.account import AccountCreate, OwnershipCreate
from app.schemas.member import MemberCreate
from app.services.conflict_service import ConflictService

MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB (Whisper's own per-file limit)
MIN_AUDIO_BYTES = 1024  # reject empty/near-empty files
ALLOWED_AUDIO_PREFIXES = ("audio/", "video/")  # video/* often carries audio
MIN_TRANSCRIPT_WORDS = 3

NUMERIC_FIELDS = {"income", "net_worth", "liquid_net_worth"}
CASE_INSENSITIVE_FIELDS = {"risk_tolerance", "preferences", "tax_bracket"}
FINANCIAL_FIELDS = [
    "income", "net_worth", "liquid_net_worth", "expense_range",
    "tax_bracket", "risk_tolerance", "time_horizon", "goals", "preferences",
]
# Member fields we compare (name is the matching key, so we diff everything else).
MEMBER_DIFF_FIELDS = [
    "date_of_birth", "email", "phone", "member_relationship", "address",
]


def _normalize_for_compare(field: str, value) -> str | None:
    """
    Return a canonical form for equality comparison.
    Numerics → Decimal string (trimmed trailing zeros).
    Free-text → trimmed; optionally case-folded for fields where casing
    is cosmetic (e.g. "aggressive" vs "Aggressive").
    """
    if value is None:
        return None
    if field in NUMERIC_FIELDS:
        try:
            return str(Decimal(str(value)).normalize())
        except InvalidOperation:
            return str(value).strip()
    text = str(value).strip()
    if field in CASE_INSENSITIVE_FIELDS:
        text = text.casefold()
    return text


class AudioService:
    def __init__(
        self,
        household_repo: HouseholdRepository,
        conflict_service: ConflictService,
        member_repo: MemberRepository,
        account_repo: AccountRepository,
    ) -> None:
        self.household_repo = household_repo
        self.conflict_service = conflict_service
        self.member_repo = member_repo
        self.account_repo = account_repo
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    @logfire.instrument("audio.process_audio", extract_args=False)
    async def process_audio(
        self,
        household_id: uuid.UUID,
        file: UploadFile,
        job_id: str | None = None,
    ) -> dict:
        def _step(msg: str) -> None:
            if job_id:
                job_store.append_step(job_id, msg)

        logfire.info(
            "audio.upload_received",
            household_id=str(household_id),
            filename=file.filename,
            job_id=job_id,
        )
        household = await self.household_repo.get_by_id(household_id)
        if not household:
            raise ValueError(f"Household {household_id} not found")

        _step(f"Processing audio for: {household.name}")

        content_type = (file.content_type or "").lower()
        if content_type and not content_type.startswith(ALLOWED_AUDIO_PREFIXES):
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported content type: {content_type}. Expected audio/* or video/*.",
            )

        _step("Reading audio file…")
        audio_bytes = await file.read()
        size = len(audio_bytes)
        if size < MIN_AUDIO_BYTES:
            raise HTTPException(status_code=400, detail="Audio file is empty or too small.")
        if size > MAX_AUDIO_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Audio file exceeds {MAX_AUDIO_BYTES // (1024 * 1024)} MB limit.",
            )

        _step(f"File size: {size // 1024} KB — sending to Whisper…")
        with logfire.span("audio.whisper_transcription", size_kb=size // 1024):
            transcription = await self.openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=(file.filename or "audio.mp3", audio_bytes, file.content_type or "audio/mpeg"),
            )
        transcript_text = (transcription.text or "").strip()
        word_count = len(transcript_text.split())
        logfire.info("audio.transcription_complete", word_count=word_count)
        _step(f"Transcription complete — {word_count} words")

        if word_count < MIN_TRANSCRIPT_WORDS:
            _step("Transcript too short to extract anything — skipping extraction.")
            return {
                "transcript_text": transcript_text,
                "updates_applied": 0,
                "conflicts_created": 0,
                "members_added": 0,
                "accounts_added": 0,
            }

        _step("Running GPT extraction with household context…")
        household_context = {f: getattr(household, f) for f in FINANCIAL_FIELDS}
        prompt = build_extraction_prompt(household_context, transcript_text)

        with logfire.span("audio.gpt_extraction", household_id=str(household_id)):
            result = await audio_extraction_agent.run(prompt)
        extracted: ExtractedHouseholdData = result.output
        _step(
            "Extraction complete — "
            f"{sum(1 for f in FINANCIAL_FIELDS if getattr(extracted, f) is not None)} household fields, "
            f"{len(extracted.members)} member(s), "
            f"{len(extracted.financial_accounts)} account(s)"
        )

        # ── 1. Household-level fields ───────────────────────────────
        updates_applied, conflicts_created = await self._apply_household_fields(
            household_id, household, extracted, _step
        )

        # ── 2. Members ──────────────────────────────────────────────
        members_added, member_id_by_name, member_conflicts = await self._apply_members(
            household_id, extracted.members, _step
        )
        conflicts_created += member_conflicts

        # ── 3. Financial accounts ───────────────────────────────────
        accounts_added = await self._apply_accounts(
            household_id, extracted.financial_accounts, member_id_by_name, _step
        )

        # Single transaction for everything extracted from this transcript.
        # All prior writes used commit=False; we commit once so the whole audio
        # ingest is atomic and we only pay one pgbouncer connect round-trip.
        try:
            await self.household_repo.db.commit()
        except Exception as exc:
            await self.household_repo.db.rollback()
            logfire.error(
                "audio.commit_failed",
                household_id=str(household_id),
                error=str(exc),
            )
            raise

        logfire.info(
            "audio.processing_complete",
            household_id=str(household_id),
            updates_applied=updates_applied,
            conflicts_created=conflicts_created,
            members_added=members_added,
            accounts_added=accounts_added,
        )
        _step(
            f"Done — {updates_applied} household update{'s' if updates_applied != 1 else ''}, "
            f"{members_added} member{'s' if members_added != 1 else ''} added, "
            f"{accounts_added} account{'s' if accounts_added != 1 else ''} added, "
            f"{conflicts_created} conflict{'s' if conflicts_created != 1 else ''} flagged"
        )

        return {
            "transcript_text": transcript_text,
            "updates_applied": updates_applied,
            "conflicts_created": conflicts_created,
            "members_added": members_added,
            "accounts_added": accounts_added,
        }

    async def _apply_household_fields(
        self,
        household_id: uuid.UUID,
        household,
        extracted: ExtractedHouseholdData,
        _step,
    ) -> tuple[int, int]:
        """Apply direct updates for empty fields, raise conflicts for differing ones."""
        updates_applied = 0
        conflicts_created = 0
        direct_updates: dict = {}

        for field in FINANCIAL_FIELDS:
            incoming_val = getattr(extracted, field)
            if incoming_val is None:
                continue
            existing_val = getattr(household, field)
            quote = extracted.quotes.get(field)

            if existing_val is None:
                direct_updates[field] = incoming_val
                updates_applied += 1
                _step(f"Applying new value → {field}: {incoming_val}")
                continue

            if _normalize_for_compare(field, incoming_val) == _normalize_for_compare(field, existing_val):
                continue

            await self.conflict_service.create_conflict(
                household_id=household_id,
                field=field,
                existing=str(existing_val),
                incoming=str(incoming_val),
                source="audio",
                source_quote=quote,
                commit=False,
            )
            conflicts_created += 1
            _step(f"Conflict flagged → {field}: {existing_val!r} vs {incoming_val!r}")

        if direct_updates:
            await self.household_repo.update(household_id, direct_updates, commit=False)

        return updates_applied, conflicts_created

    async def _apply_members(
        self,
        household_id: uuid.UUID,
        members: list[ExtractedMember],
        _step,
    ) -> tuple[int, dict[str, uuid.UUID], int]:
        """Create NEW members; backfill null fields on existing ones; flag conflicts
        when extracted values differ from existing non-null values.

        Returns (members_added, name → member_id map, conflicts_created).
        """
        members_added = 0
        conflicts_created = 0
        name_to_id: dict[str, uuid.UUID] = {}

        for m in members:
            raw_name = (m.name or "").strip()
            if not raw_name:
                continue

            existing = await self.member_repo.find_by_name_in_household(
                household_id, raw_name, date_of_birth=m.date_of_birth
            )

            if existing is None:
                created = await self.member_repo.create(
                    household_id,
                    MemberCreate(
                        name=raw_name,
                        date_of_birth=m.date_of_birth,
                        email=m.email,
                        phone=m.phone,
                        member_relationship=m.member_relationship,
                        address=m.address,
                    ),
                    commit=False,
                )
                members_added += 1
                name_to_id[raw_name.lower()] = created.id
                _step(f"Member added → {raw_name}")
                continue

            # Existing member — backfill null fields, conflict on differing ones.
            name_to_id[raw_name.lower()] = existing.id
            backfill: dict = {}
            for field in MEMBER_DIFF_FIELDS:
                incoming = getattr(m, field)
                if incoming is None:
                    continue
                existing_val = getattr(existing, field)
                if existing_val is None:
                    backfill[field] = incoming
                    continue
                if str(existing_val).strip().casefold() == str(incoming).strip().casefold():
                    continue
                # Differ — flag as a conflict. We scope the field name to the member
                # so the advisor knows which record is affected.
                field_label = f"member:{raw_name}:{field}"
                await self.conflict_service.create_conflict(
                    household_id=household_id,
                    field=field_label,
                    existing=str(existing_val),
                    incoming=str(incoming),
                    source="audio",
                    source_quote=m.source_quote,
                    commit=False,
                )
                conflicts_created += 1
                _step(f"Conflict flagged → {field_label}: {existing_val!r} vs {incoming!r}")

            if backfill:
                await self.member_repo.update(existing.id, backfill, commit=False)
                _step(f"Member backfilled → {raw_name}: {', '.join(backfill.keys())}")

        return members_added, name_to_id, conflicts_created

    async def _apply_accounts(
        self,
        household_id: uuid.UUID,
        accounts: list[ExtractedAccount],
        member_id_by_name: dict[str, uuid.UUID],
        _step,
    ) -> int:
        """Create accounts that don't already exist on the household. Dedup by
        account_number when present, else by account_type + custodian."""
        accounts_added = 0

        for acc in accounts:
            existing = None
            if acc.account_number:
                existing = await self.account_repo.find_by_account_number(
                    household_id, acc.account_number
                )
            elif acc.account_type:
                existing = await self.account_repo.find_by_type_in_household(
                    household_id, acc.account_type
                )
                # Same type but different custodian → treat as a DIFFERENT account
                # (e.g. multiple brokerage accounts at different firms).
                if existing and acc.custodian and existing.custodian:
                    if existing.custodian.strip().casefold() != acc.custodian.strip().casefold():
                        existing = None

            if existing:
                continue
            if not (acc.account_number or acc.account_type or acc.custodian):
                continue  # nothing to anchor on — skip

            ownerships: list[OwnershipCreate] = []
            for owner in acc.owner_names:
                member_id = member_id_by_name.get(owner.strip().lower())
                if member_id is None:
                    # Try a looser lookup against the existing household roster.
                    found = await self.member_repo.find_by_name_in_household(
                        household_id, owner
                    )
                    if found:
                        member_id = found.id
                        member_id_by_name[owner.strip().lower()] = found.id
                if member_id is not None:
                    ownerships.append(
                        OwnershipCreate(member_id=member_id, ownership_percentage=None)
                    )

            await self.account_repo.create(
                household_id,
                AccountCreate(
                    account_number=acc.account_number,
                    custodian=acc.custodian,
                    account_type=acc.account_type,
                    account_value=acc.account_value,
                    ownerships=ownerships,
                ),
                commit=False,
            )
            accounts_added += 1
            descriptor = acc.account_type or acc.custodian or "account"
            _step(f"Account added → {descriptor}")

        return accounts_added
