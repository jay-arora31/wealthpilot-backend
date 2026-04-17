import logfire
from fastapi import APIRouter, Depends

from app.api.deps import get_admin_service
from app.services.admin_service import AdminService

router = APIRouter()


@router.delete("/reset")
async def reset_all_data(service: AdminService = Depends(get_admin_service)):
    """Delete every household (cascades to all related data). Irreversible."""
    logfire.warning("route.admin_reset_all_data")
    return await service.delete_all_data()
