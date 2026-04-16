import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import AccountOwnership


class AccountOwnershipRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self, account_id: uuid.UUID, member_id: uuid.UUID, percentage: Decimal | None
    ) -> AccountOwnership:
        ao = AccountOwnership(account_id=account_id, member_id=member_id, ownership_percentage=percentage)
        self.db.add(ao)
        await self.db.commit()
        await self.db.refresh(ao)
        return ao

    async def list_by_account(self, account_id: uuid.UUID) -> list[AccountOwnership]:
        result = await self.db.execute(
            select(AccountOwnership).where(AccountOwnership.account_id == account_id)
        )
        return list(result.scalars().all())
