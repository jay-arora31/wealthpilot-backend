import uuid

from fastapi import APIRouter, HTTPException

from app.core.jobs import JobStatus, get_job

router = APIRouter()


@router.get("/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: uuid.UUID):
    job = get_job(str(job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(**job)
