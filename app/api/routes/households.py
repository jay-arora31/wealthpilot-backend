import asyncio
import uuid

import logfire
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status

from app.api.deps import get_household_service, get_household_repo, get_insight_service
from app.repositories.household_repo import HouseholdRepository
from app.core import jobs as job_store
from app.schemas.household import HouseholdCreate, HouseholdDetail, HouseholdSummary, HouseholdUpdate
from app.schemas.insight import InsightsResponse
from app.services.audio_service import AudioService
from app.services.excel_service import ExcelService
from app.services.household_service import HouseholdService
from app.services.insight_service import InsightService


router = APIRouter()


@router.get("", response_model=list[HouseholdSummary])
async def list_households(service: HouseholdService = Depends(get_household_service)):
    return await service.list_households()


@router.post("", response_model=HouseholdDetail, status_code=status.HTTP_201_CREATED)
async def create_household(data: HouseholdCreate, service: HouseholdService = Depends(get_household_service)):
    return await service.create_household(data)


@router.get("/insights", response_model=InsightsResponse)
async def get_insights(service: InsightService = Depends(get_insight_service)):
    return await service.get_insights()


@router.post("/upload-excel", status_code=status.HTTP_202_ACCEPTED)
async def upload_excel(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    if not (file.filename or "").endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) are accepted")

    # Read file bytes NOW (before background task — UploadFile is not safe to pass across tasks)
    content = await file.read()
    filename = file.filename or "upload.xlsx"
    headers = file.headers

    job_id = job_store.create_job("excel")
    job_store.update_job(job_id, status="running")
    job_store.append_step(job_id, f"Received: {filename}")
    logfire.info("route.upload_excel_accepted", filename=filename, job_id=job_id)

    async def _run():
        import io
        from starlette.datastructures import UploadFile as StarletteUploadFile
        from app.core.database import async_session_factory
        from app.repositories.account_repo import AccountRepository
        from app.repositories.bank_detail_repo import BankDetailRepository
        from app.repositories.household_repo import HouseholdRepository
        from app.repositories.member_repo import MemberRepository
        from app.repositories.conflict_repo import ConflictRepository
        from app.services.conflict_service import ConflictService

        try:
            # Create a fresh DB session owned entirely by this background task
            async with async_session_factory() as db:
                svc = ExcelService(
                    household_repo=HouseholdRepository(db),
                    member_repo=MemberRepository(db),
                    account_repo=AccountRepository(db),
                    bank_detail_repo=BankDetailRepository(db),
                    conflict_service=ConflictService(
                        ConflictRepository(db), HouseholdRepository(db), MemberRepository(db)
                    ),
                )
                fake_file = StarletteUploadFile(
                    filename=filename,
                    file=io.BytesIO(content),
                    headers=headers,
                )
                result = await svc.process_excel(fake_file, job_id=job_id)
            job_store.mark_done(job_id, result)
            logfire.info("route.upload_excel_done", job_id=job_id, result=result)
        except Exception as exc:
            logfire.error("route.upload_excel_failed", job_id=job_id, error=str(exc))
            job_store.mark_failed(job_id, str(exc))

    background_tasks.add_task(_run)
    return {"job_id": job_id}


@router.get("/{household_id}", response_model=HouseholdDetail)
async def get_household(household_id: uuid.UUID, service: HouseholdService = Depends(get_household_service)):
    return await service.get_household(household_id)


@router.put("/{household_id}", response_model=HouseholdDetail)
async def update_household(
    household_id: uuid.UUID,
    data: HouseholdUpdate,
    service: HouseholdService = Depends(get_household_service),
):
    return await service.update_household(household_id, data)


@router.delete("/{household_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_household(household_id: uuid.UUID, service: HouseholdService = Depends(get_household_service)):
    await service.delete_household(household_id)


@router.post("/{household_id}/upload-audio", status_code=status.HTTP_202_ACCEPTED)
async def upload_audio(
    household_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    force: bool = False,
    household_repo: HouseholdRepository = Depends(get_household_repo),
):
    # Validate household exists before queuing the background job
    if not await household_repo.get_by_id(household_id):
        raise HTTPException(status_code=404, detail="Household not found")

    allowed = (".mp3", ".wav", ".m4a", ".webm", ".mp4", ".ogg")
    filename = file.filename or ""
    if not filename.endswith(allowed):
        raise HTTPException(status_code=400, detail=f"Audio format not supported. Accepted: {allowed}")

    # Read bytes immediately — UploadFile cannot be passed to background task safely
    content = await file.read()
    headers = file.headers

    job_id = job_store.create_job("audio")
    job_store.update_job(job_id, status="running")
    job_store.append_step(job_id, f"Received: {filename}")
    logfire.info("route.upload_audio_accepted", household_id=str(household_id), filename=filename, job_id=job_id)

    async def _run():
        import io
        from starlette.datastructures import UploadFile as StarletteUploadFile
        from app.core.database import async_session_factory
        from app.repositories.account_repo import AccountRepository
        from app.repositories.household_repo import HouseholdRepository
        from app.repositories.conflict_repo import ConflictRepository
        from app.repositories.member_repo import MemberRepository
        from app.services.conflict_service import ConflictService

        try:
            # Create a fresh DB session owned entirely by this background task
            async with async_session_factory() as db:
                svc = AudioService(
                    household_repo=HouseholdRepository(db),
                    conflict_service=ConflictService(
                        ConflictRepository(db), HouseholdRepository(db), MemberRepository(db)
                    ),
                    member_repo=MemberRepository(db),
                    account_repo=AccountRepository(db),
                )
                fake_file = StarletteUploadFile(
                    filename=filename,
                    file=io.BytesIO(content),
                    headers=headers,
                )
                result = await svc.process_audio(
                    household_id, fake_file, job_id=job_id, force=force
                )
            job_store.mark_done(job_id, result)
            logfire.info("route.upload_audio_done", job_id=job_id, result=result)
        except Exception as exc:
            logfire.error("route.upload_audio_failed", job_id=job_id, error=str(exc))
            job_store.mark_failed(job_id, str(exc))

    background_tasks.add_task(_run)
    return {"job_id": job_id}
