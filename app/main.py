import logging

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# config must be imported first so LOGFIRE_TOKEN is set in the environment
from app.core.config import settings  # noqa: F401 — side-effect: sets env vars
from app.api.routes import accounts, admin, bank_details, conflicts, households, jobs, members

logger = logging.getLogger(__name__)

try:
    logfire.configure(
        token=settings.LOGFIRE_API_KEY or None,
        service_name="fasttrackr-ai-backend",
        send_to_logfire=bool(settings.LOGFIRE_API_KEY),
    )
except Exception as exc:  # never let monitoring setup crash the app
    logger.warning("logfire setup failed (continuing without it): %s", exc)

app = FastAPI(title="FastTrackr AI", version="0.1.0")

try:
    logfire.instrument_fastapi(app, capture_headers=True)
except Exception as exc:
    logger.warning("logfire FastAPI instrumentation failed: %s", exc)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(households.router, prefix="/api/households", tags=["Households"])
app.include_router(members.router, prefix="/api", tags=["Members"])
app.include_router(accounts.router, prefix="/api", tags=["Accounts"])
app.include_router(conflicts.router, prefix="/api", tags=["Conflicts"])
app.include_router(bank_details.router, prefix="/api", tags=["BankDetails"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
