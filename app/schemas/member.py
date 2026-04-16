import uuid
from datetime import datetime

from pydantic import BaseModel


class MemberCreate(BaseModel):
    name: str
    date_of_birth: str | None = None
    email: str | None = None
    phone: str | None = None
    member_relationship: str | None = None
    address: str | None = None


class MemberUpdate(BaseModel):
    name: str | None = None
    date_of_birth: str | None = None
    email: str | None = None
    phone: str | None = None
    member_relationship: str | None = None
    address: str | None = None


class MemberResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    household_id: uuid.UUID
    name: str
    date_of_birth: str | None = None
    email: str | None = None
    phone: str | None = None
    member_relationship: str | None = None
    address: str | None = None
    created_at: datetime
