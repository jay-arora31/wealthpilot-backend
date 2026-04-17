import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Member
from app.schemas.member import MemberCreate


class MemberRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_by_household(self, household_id: uuid.UUID) -> list[Member]:
        result = await self.db.execute(select(Member).where(Member.household_id == household_id))
        return list(result.scalars().all())

    async def get_by_id(self, id: uuid.UUID) -> Member | None:
        result = await self.db.execute(select(Member).where(Member.id == id))
        return result.scalar_one_or_none()

    async def create(
        self, household_id: uuid.UUID, data: MemberCreate, commit: bool = True
    ) -> Member:
        member = Member(household_id=household_id, **data.model_dump())
        self.db.add(member)
        if commit:
            await self.db.commit()
            await self.db.refresh(member)
        else:
            await self.db.flush()
        return member

    async def update(
        self, member_id: uuid.UUID, data: dict, commit: bool = True
    ) -> Member | None:
        member = await self.get_by_id(member_id)
        if not member:
            return None
        for key, value in data.items():
            setattr(member, key, value)
        if commit:
            await self.db.commit()
            await self.db.refresh(member)
        else:
            await self.db.flush()
        return member

    async def delete(self, member_id: uuid.UUID, commit: bool = True) -> None:
        member = await self.get_by_id(member_id)
        if member:
            await self.db.delete(member)
            if commit:
                await self.db.commit()

    async def update_dob(
        self, member_id: uuid.UUID, date_of_birth: str, commit: bool = True
    ) -> None:
        member = await self.get_by_id(member_id)
        if member:
            member.date_of_birth = date_of_birth
            if commit:
                await self.db.commit()
            else:
                await self.db.flush()

    async def find_by_name_in_household(
        self,
        household_id: uuid.UUID,
        name: str,
        date_of_birth: str | None = None,
    ) -> Member | None:
        # Always search by name first
        result = await self.db.execute(
            select(Member).where(
                Member.household_id == household_id,
                func.lower(Member.name) == name.lower().strip(),
            )
        )
        matches = list(result.scalars().all())

        if not matches:
            return None
        if len(matches) == 1:
            return matches[0]

        # Multiple members share the same name — use DOB as tiebreaker only when
        # the incoming DOB is known and at least one stored record has a matching DOB.
        if date_of_birth is not None:
            dob_match = next((m for m in matches if m.date_of_birth == date_of_birth), None)
            if dob_match:
                return dob_match

        # Fall back to the first match (oldest record)
        return matches[0]
