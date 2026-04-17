import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import AccountOwnership, FinancialAccount, Household, Member
from app.schemas.household import HouseholdCreate, HouseholdUpdate


class HouseholdRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_all(self) -> list[Household]:
        result = await self.db.execute(select(Household))
        return list(result.scalars().all())

    async def list_with_member_counts(self) -> list[tuple[Household, int]]:
        """Single query returning all households with their member counts — avoids N+1."""
        stmt = (
            select(Household, func.count(Member.id).label("member_count"))
            .outerjoin(Member, Member.household_id == Household.id)
            .group_by(Household.id)
        )
        result = await self.db.execute(stmt)
        return [(row.Household, row.member_count) for row in result.all()]

    async def get_by_id(self, id: uuid.UUID) -> Household | None:
        result = await self.db.execute(select(Household).where(Household.id == id))
        return result.scalar_one_or_none()

    async def get_by_id_with_relations(self, id: uuid.UUID) -> Household | None:
        """Load household + all relations in 3 batched selectin queries instead of lazy-loading."""
        stmt = (
            select(Household)
            .where(Household.id == id)
            .options(
                selectinload(Household.members),
                selectinload(Household.financial_accounts).selectinload(FinancialAccount.ownerships),
                selectinload(Household.bank_details),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_name(self, name: str) -> Household | None:
        result = await self.db.execute(
            select(Household).where(func.lower(Household.name) == name.lower().strip())
        )
        return result.scalar_one_or_none()

    async def create(self, data: HouseholdCreate, commit: bool = True) -> Household:
        household = Household(**data.model_dump())
        self.db.add(household)
        if commit:
            await self.db.commit()
            await self.db.refresh(household)
        else:
            # Flush populates the generated PK without ending the transaction,
            # so callers that are batching multiple writes can keep a single
            # connection/transaction across repo calls.
            await self.db.flush()
        return household

    async def update(self, id: uuid.UUID, data: dict, commit: bool = True) -> Household | None:
        household = await self.get_by_id(id)
        if not household:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(household, key, value)
        if commit:
            await self.db.commit()
            await self.db.refresh(household)
        else:
            await self.db.flush()
        return household

    async def delete(self, id: uuid.UUID, commit: bool = True) -> None:
        household = await self.get_by_id(id)
        if household:
            await self.db.delete(household)
            if commit:
                await self.db.commit()

    async def count_members(self, household_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count(Member.id)).where(Member.household_id == household_id)
        )
        return result.scalar_one()
