import uuid
from decimal import Decimal, InvalidOperation

import logfire
from fastapi import HTTPException

from app.repositories.conflict_repo import ConflictRepository
from app.repositories.household_repo import HouseholdRepository
from app.repositories.member_repo import MemberRepository
from app.schemas.conflict import ConflictResponse

_DECIMAL_FIELDS = {"income", "net_worth", "liquid_net_worth"}
# Conflicts whose field_name starts with this prefix target a MEMBER row rather
# than the household row. Format: "member:<member name>:<field>".
_MEMBER_FIELD_PREFIX = "member:"


def _cast_incoming(field_name: str, raw: str | None):
    """Cast the stored string back to the correct Python type for the DB column."""
    if raw is None:
        return None
    if field_name in _DECIMAL_FIELDS:
        try:
            return Decimal(raw)
        except InvalidOperation:
            return raw
    return raw


class ConflictService:
    def __init__(
        self,
        conflict_repo: ConflictRepository,
        household_repo: HouseholdRepository,
        member_repo: MemberRepository | None = None,
    ) -> None:
        self.conflict_repo = conflict_repo
        self.household_repo = household_repo
        self.member_repo = member_repo

    @logfire.instrument("conflict.list_pending", extract_args=True)
    async def list_pending(self, household_id: uuid.UUID) -> list[ConflictResponse]:
        conflicts = await self.conflict_repo.list_pending_by_household(household_id)
        result = [ConflictResponse.model_validate(c) for c in conflicts]
        logfire.info("conflict.list_returned", household_id=str(household_id), count=len(result))
        return result

    @logfire.instrument("conflict.create", extract_args=False)
    async def create_conflict(
        self,
        household_id: uuid.UUID,
        field: str,
        existing: str | None,
        incoming: str | None,
        source: str,
        source_quote: str | None = None,
        commit: bool = True,
    ) -> ConflictResponse:
        conflict = await self.conflict_repo.create(
            household_id=household_id,
            field_name=field,
            existing_value=existing,
            incoming_value=incoming,
            source=source,
            source_quote=source_quote,
            commit=commit,
        )
        logfire.info(
            "conflict.created",
            household_id=str(household_id),
            conflict_id=str(conflict.id),
            field=field,
            source=source,
        )
        return ConflictResponse.model_validate(conflict)

    @logfire.instrument("conflict.resolve", extract_args=True)
    async def resolve_conflict(self, conflict_id: uuid.UUID, action: str) -> ConflictResponse:
        conflict = await self.conflict_repo.get_by_id(conflict_id)
        if not conflict:
            logfire.warning("conflict.not_found", conflict_id=str(conflict_id))
            raise HTTPException(status_code=404, detail="Conflict not found")

        if action == "accept":
            if conflict.field_name.startswith(_MEMBER_FIELD_PREFIX):
                # Format: "member:<name>:<field>"
                _, member_name, member_field = conflict.field_name.split(":", 2)
                if self.member_repo is not None:
                    member = await self.member_repo.find_by_name_in_household(
                        conflict.household_id, member_name
                    )
                    if member is not None:
                        await self.member_repo.update(
                            member.id, {member_field: conflict.incoming_value}
                        )
            else:
                typed_value = _cast_incoming(conflict.field_name, conflict.incoming_value)
                await self.household_repo.update(
                    conflict.household_id, {conflict.field_name: typed_value}
                )

        resolved = await self.conflict_repo.resolve(conflict_id, action)
        logfire.info(
            "conflict.resolved",
            conflict_id=str(conflict_id),
            action=action,
            field=conflict.field_name,
            household_id=str(conflict.household_id),
        )
        return ConflictResponse.model_validate(resolved)
