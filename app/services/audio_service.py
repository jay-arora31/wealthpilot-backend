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
"""
import uuid
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException, UploadFile
from openai import AsyncOpenAI

from app.agents.audio_extraction import (
    ExtractedHouseholdData,
    audio_extraction_agent,
    build_extraction_prompt,
)
from app.core import jobs as job_store
from app.core.config import settings
from app.repositories.household_repo import HouseholdRepository
from app.services.conflict_service import ConflictService

# Upload guardrails — fail fast before spending a Whisper call.
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB (Whisper's own per-file limit)
MIN_AUDIO_BYTES = 1024  # reject empty/near-empty files
ALLOWED_AUDIO_PREFIXES = ("audio/", "video/")  # video/* is allowed because .mp4/.webm often carry audio
MIN_TRANSCRIPT_WORDS = 3

NUMERIC_FIELDS = {"income", "net_worth", "liquid_net_worth"}
# Fields where we treat the extracted text case-insensitively before comparing.
CASE_INSENSITIVE_FIELDS = {"risk_tolerance", "preferences", "tax_bracket"}
FINANCIAL_FIELDS = [
    "income", "net_worth", "liquid_net_worth", "expense_range",
    "tax_bracket", "risk_tolerance", "time_horizon", "goals", "preferences",
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
    def __init__(self, household_repo: HouseholdRepository, conflict_service: ConflictService) -> None:
        self.household_repo = household_repo
        self.conflict_service = conflict_service
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def process_audio(
        self,
        household_id: uuid.UUID,
        file: UploadFile,
        job_id: str | None = None,
    ) -> dict:
        def _step(msg: str) -> None:
            if job_id:
                job_store.append_step(job_id, msg)

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
        transcription = await self.openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=(file.filename or "audio.mp3", audio_bytes, file.content_type or "audio/mpeg"),
        )
        transcript_text = (transcription.text or "").strip()
        word_count = len(transcript_text.split())
        _step(f"Transcription complete — {word_count} words")

        if word_count < MIN_TRANSCRIPT_WORDS:
            _step("Transcript too short to extract anything — skipping extraction.")
            return {
                "transcript_text": transcript_text,
                "updates_applied": 0,
                "conflicts_created": 0,
            }

        _step("Running GPT extraction with household context…")
        household_context = {f: getattr(household, f) for f in FINANCIAL_FIELDS}
        prompt = build_extraction_prompt(household_context, transcript_text)

        result = await audio_extraction_agent.run(prompt)
        extracted: ExtractedHouseholdData = result.output
        _step("Extraction complete — comparing against existing data…")

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
            )
            conflicts_created += 1
            _step(f"Conflict flagged → {field}: {existing_val!r} vs {incoming_val!r}")

        if direct_updates:
            await self.household_repo.update(household_id, direct_updates)

        _step(
            f"Done — {updates_applied} update{'s' if updates_applied != 1 else ''} applied, "
            f"{conflicts_created} conflict{'s' if conflicts_created != 1 else ''} flagged"
        )

        return {
            "transcript_text": transcript_text,
            "updates_applied": updates_applied,
            "conflicts_created": conflicts_created,
        }
