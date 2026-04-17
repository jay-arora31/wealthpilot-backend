import uuid

import logfire
from fastapi import APIRouter, HTTPException

from app.core.jobs import JobStatus, get_job

router = APIRouter()


@router.get("/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: uuid.UUID):
    job = get_job(str(job_id))
    if not job:
        logfire.warning("job.not_found", job_id=str(job_id))
        raise HTTPException(status_code=404, detail="Job not found")
    logfire.info("job.status_checked", job_id=str(job_id), status=job.get("status"))
    return JobStatus(**job)
