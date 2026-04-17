import uuid

import logfire
from fastapi import APIRouter, Depends

from app.api.deps import get_conflict_service
from app.schemas.conflict import ConflictResponse, ConflictResolveRequest
from app.services.conflict_service import ConflictService

router = APIRouter()


@router.get("/households/{household_id}/conflicts", response_model=list[ConflictResponse])
async def list_conflicts(household_id: uuid.UUID, service: ConflictService = Depends(get_conflict_service)):
    logfire.info("route.list_conflicts", household_id=str(household_id))
    return await service.list_pending(household_id)


@router.post("/conflicts/{conflict_id}/resolve", response_model=ConflictResponse)
async def resolve_conflict(
    conflict_id: uuid.UUID,
    data: ConflictResolveRequest,
    service: ConflictService = Depends(get_conflict_service),
):
    logfire.info("route.resolve_conflict", conflict_id=str(conflict_id), action=data.action)
    return await service.resolve_conflict(conflict_id, data.action)
