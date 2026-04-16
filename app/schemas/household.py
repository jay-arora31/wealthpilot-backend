import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.account import AccountResponse
from app.schemas.bank_detail import BankDetailResponse
from app.schemas.member import MemberResponse


class HouseholdCreate(BaseModel):
    name: str
    income: Decimal | None = None
    net_worth: Decimal | None = None
    liquid_net_worth: Decimal | None = None
    expense_range: str | None = None
    tax_bracket: str | None = None
    risk_tolerance: str | None = None
    time_horizon: str | None = None
    goals: str | None = None
    preferences: str | None = None


class HouseholdUpdate(BaseModel):
    name: str | None = None
    income: Decimal | None = None
    net_worth: Decimal | None = None
    liquid_net_worth: Decimal | None = None
    expense_range: str | None = None
    tax_bracket: str | None = None
    risk_tolerance: str | None = None
    time_horizon: str | None = None
    goals: str | None = None
    preferences: str | None = None


class HouseholdSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    income: Decimal | None = None
    net_worth: Decimal | None = None
    member_count: int = 0


class HouseholdDetail(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    income: Decimal | None = None
    net_worth: Decimal | None = None
    liquid_net_worth: Decimal | None = None
    expense_range: str | None = None
    tax_bracket: str | None = None
    risk_tolerance: str | None = None
    time_horizon: str | None = None
    goals: str | None = None
    preferences: str | None = None
    members: list[MemberResponse] = []
    financial_accounts: list[AccountResponse] = []
    bank_details: list[BankDetailResponse] = []
    pending_conflict_count: int = 0
    created_at: datetime
    updated_at: datetime
