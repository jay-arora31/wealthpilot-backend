from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import accounts, bank_details, conflicts, households, jobs, members

app = FastAPI(title="FastTrackr AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
