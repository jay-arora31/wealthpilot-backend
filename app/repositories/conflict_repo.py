import uuid
from datetime import datetime, UTC

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import DataConflict


class ConflictRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_pending_by_household(self, household_id: uuid.UUID) -> list[DataConflict]:
        result = await self.db.execute(
            select(DataConflict).where(
                DataConflict.household_id == household_id, DataConflict.status == "pending"
            )
        )
        return list(result.scalars().all())

    async def get_by_id(self, id: uuid.UUID) -> DataConflict | None:
        result = await self.db.execute(select(DataConflict).where(DataConflict.id == id))
        return result.scalar_one_or_none()

    async def find_pending_duplicate(
        self,
        household_id: uuid.UUID,
        field_name: str,
        incoming_value: str | None,
        source: str,
    ) -> DataConflict | None:
        result = await self.db.execute(
            select(DataConflict).where(
                DataConflict.household_id == household_id,
                DataConflict.field_name == field_name,
                DataConflict.incoming_value == incoming_value,
                DataConflict.source == source,
                DataConflict.status == "pending",
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        household_id: uuid.UUID,
        field_name: str,
        existing_value: str | None,
        incoming_value: str | None,
        source: str,
        source_quote: str | None = None,
    ) -> DataConflict:
        # Skip if an identical pending conflict (same field + value + source) already exists
        duplicate = await self.find_pending_duplicate(
            household_id, field_name, incoming_value, source
        )
        if duplicate:
            return duplicate

        conflict = DataConflict(
            household_id=household_id,
            field_name=field_name,
            existing_value=existing_value,
            incoming_value=incoming_value,
            source_quote=source_quote,
            source=source,
            status="pending",
        )
        self.db.add(conflict)
        await self.db.commit()
        await self.db.refresh(conflict)
        return conflict

    async def resolve(self, id: uuid.UUID, action: str) -> DataConflict | None:
        conflict = await self.get_by_id(id)
        if not conflict:
            return None
        conflict.status = "accepted" if action == "accept" else "rejected"
        conflict.resolved_at = datetime.now(UTC).replace(tzinfo=None)
        await self.db.commit()
        await self.db.refresh(conflict)
        return conflict

    async def count_pending(self, household_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count(DataConflict.id)).where(
                DataConflict.household_id == household_id, DataConflict.status == "pending"
            )
        )
        return result.scalar_one()
