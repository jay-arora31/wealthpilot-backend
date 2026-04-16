import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import BankDetail
from app.schemas.bank_detail import BankDetailCreate


class BankDetailRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_by_household(self, household_id: uuid.UUID) -> list[BankDetail]:
        result = await self.db.execute(select(BankDetail).where(BankDetail.household_id == household_id))
        return list(result.scalars().all())

    async def get_by_id(self, id: uuid.UUID) -> BankDetail | None:
        result = await self.db.execute(select(BankDetail).where(BankDetail.id == id))
        return result.scalar_one_or_none()

    async def update(self, bank_id: uuid.UUID, data: dict) -> BankDetail | None:
        bd = await self.get_by_id(bank_id)
        if not bd:
            return None
        for key, value in data.items():
            setattr(bd, key, value)
        await self.db.commit()
        await self.db.refresh(bd)
        return bd

    async def delete(self, bank_id: uuid.UUID) -> None:
        bd = await self.get_by_id(bank_id)
        if bd:
            await self.db.delete(bd)
            await self.db.commit()

    async def create(self, household_id: uuid.UUID, data: BankDetailCreate) -> BankDetail:
        bd = BankDetail(household_id=household_id, **data.model_dump())
        self.db.add(bd)
        await self.db.commit()
        await self.db.refresh(bd)
        return bd
