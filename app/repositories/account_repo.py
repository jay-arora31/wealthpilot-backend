import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import AccountOwnership, FinancialAccount
from app.schemas.account import AccountCreate


class AccountRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_by_household(self, household_id: uuid.UUID) -> list[FinancialAccount]:
        result = await self.db.execute(
            select(FinancialAccount).where(FinancialAccount.household_id == household_id)
        )
        return list(result.scalars().all())

    async def find_by_account_number(
        self, household_id: uuid.UUID, account_number: str
    ) -> FinancialAccount | None:
        result = await self.db.execute(
            select(FinancialAccount).where(
                FinancialAccount.household_id == household_id,
                FinancialAccount.account_number == account_number,
            )
        )
        return result.scalar_one_or_none()

    async def find_by_type_in_household(
        self, household_id: uuid.UUID, account_type: str
    ) -> FinancialAccount | None:
        """Find an existing account by type (used when no account number is available)."""
        from sqlalchemy import func
        result = await self.db.execute(
            select(FinancialAccount).where(
                FinancialAccount.household_id == household_id,
                func.lower(FinancialAccount.account_type) == account_type.lower().strip(),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, id: uuid.UUID) -> FinancialAccount | None:
        result = await self.db.execute(select(FinancialAccount).where(FinancialAccount.id == id))
        return result.scalar_one_or_none()

    async def update(self, account_id: uuid.UUID, data: dict) -> FinancialAccount | None:
        account = await self.get_by_id(account_id)
        if not account:
            return None
        for key, value in data.items():
            setattr(account, key, value)
        await self.db.commit()
        await self.db.refresh(account)
        return account

    async def delete(self, account_id: uuid.UUID) -> None:
        account = await self.get_by_id(account_id)
        if account:
            await self.db.delete(account)
            await self.db.commit()

    async def create(self, household_id: uuid.UUID, data: AccountCreate) -> FinancialAccount:
        account_data = data.model_dump(exclude={"ownerships"})
        account = FinancialAccount(household_id=household_id, **account_data)
        self.db.add(account)
        await self.db.flush()

        for ownership in data.ownerships:
            ao = AccountOwnership(
                account_id=account.id,
                member_id=ownership.member_id,
                ownership_percentage=ownership.ownership_percentage,
            )
            self.db.add(ao)

        await self.db.commit()
        await self.db.refresh(account)
        return account
