import uuid

from app.repositories.member_repo import MemberRepository
from app.schemas.member import MemberCreate, MemberResponse


class MemberService:
    def __init__(self, repo: MemberRepository) -> None:
        self.repo = repo

    async def list_members(self, household_id: uuid.UUID) -> list[MemberResponse]:
        members = await self.repo.list_by_household(household_id)
        return [MemberResponse.model_validate(m) for m in members]

    async def add_member(self, household_id: uuid.UUID, data: MemberCreate) -> MemberResponse:
        member = await self.repo.create(household_id, data)
        return MemberResponse.model_validate(member)
