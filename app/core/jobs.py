"""
In-memory background job store.

Each job goes through these states:
  queued → running → done | failed

The `steps` list tracks fine-grained progress messages so the frontend
can show a live log while waiting.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel


class JobStatus(BaseModel):
    job_id: str
    status: str          # queued | running | done | failed
    job_type: str        # excel | audio
    steps: list[str]     # ordered log of progress messages
    result: dict | None = None
    error: str | None = None
    created_at: str
    updated_at: str


# Global store — keyed by job_id string
_jobs: dict[str, dict[str, Any]] = {}


def create_job(job_type: str) -> str:
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "job_type": job_type,
        "steps": [],
        "result": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    return job_id


def get_job(job_id: str) -> dict | None:
    return _jobs.get(job_id)


def update_job(job_id: str, **kwargs: Any) -> None:
    if job_id not in _jobs:
        return
    _jobs[job_id].update(kwargs)
    _jobs[job_id]["updated_at"] = datetime.now(timezone.utc).isoformat()


def append_step(job_id: str, message: str) -> None:
    if job_id not in _jobs:
        return
    _jobs[job_id]["steps"].append(message)
    _jobs[job_id]["updated_at"] = datetime.now(timezone.utc).isoformat()


def mark_done(job_id: str, result: dict) -> None:
    update_job(job_id, status="done", result=result)


def mark_failed(job_id: str, error: str) -> None:
    update_job(job_id, status="failed", error=error)
