import uuid

import logfire

from app.repositories.member_repo import MemberRepository
from app.schemas.member import MemberCreate, MemberResponse


class MemberService:
    def __init__(self, repo: MemberRepository) -> None:
        self.repo = repo

    @logfire.instrument("member.list", extract_args=True)
    async def list_members(self, household_id: uuid.UUID) -> list[MemberResponse]:
        members = await self.repo.list_by_household(household_id)
        result = [MemberResponse.model_validate(m) for m in members]
        logfire.info("member.list_returned", household_id=str(household_id), count=len(result))
        return result

    @logfire.instrument("member.add", extract_args=True)
    async def add_member(self, household_id: uuid.UUID, data: MemberCreate) -> MemberResponse:
        member = await self.repo.create(household_id, data)
        logfire.info("member.created", household_id=str(household_id), member_id=str(member.id), name=data.name)
        return MemberResponse.model_validate(member)
