import uuid

from pydantic import BaseModel


class BankDetailCreate(BaseModel):
    bank_name: str | None = None
    account_number: str | None = None
    routing_number: str | None = None


class BankDetailUpdate(BaseModel):
    bank_name: str | None = None
    account_number: str | None = None
    routing_number: str | None = None


class BankDetailResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    household_id: uuid.UUID
    bank_name: str | None = None
    account_number: str | None = None
    routing_number: str | None = None
