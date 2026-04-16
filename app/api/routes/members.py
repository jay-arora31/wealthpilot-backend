import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_member_repo, get_member_service
from app.repositories.member_repo import MemberRepository
from app.schemas.member import MemberCreate, MemberResponse, MemberUpdate
from app.services.member_service import MemberService

router = APIRouter()


@router.get("/households/{household_id}/members", response_model=list[MemberResponse])
async def list_members(household_id: uuid.UUID, service: MemberService = Depends(get_member_service)):
    return await service.list_members(household_id)


@router.post("/households/{household_id}/members", response_model=MemberResponse, status_code=201)
async def add_member(
    household_id: uuid.UUID,
    data: MemberCreate,
    service: MemberService = Depends(get_member_service),
):
    return await service.add_member(household_id, data)


@router.put("/members/{member_id}", response_model=MemberResponse)
async def update_member(
    member_id: uuid.UUID,
    data: MemberUpdate,
    repo: MemberRepository = Depends(get_member_repo),
):
    updated = await repo.update(member_id, data.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Member not found")
    return updated


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(
    member_id: uuid.UUID,
    repo: MemberRepository = Depends(get_member_repo),
):
    member = await repo.get_by_id(member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    await repo.delete(member_id)
