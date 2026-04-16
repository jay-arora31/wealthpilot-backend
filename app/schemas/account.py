import uuid
from decimal import Decimal

from pydantic import BaseModel


class OwnershipCreate(BaseModel):
    member_id: uuid.UUID
    ownership_percentage: Decimal | None = None


class AccountCreate(BaseModel):
    account_number: str | None = None
    custodian: str | None = None
    account_type: str | None = None
    account_value: Decimal | None = None
    ownerships: list[OwnershipCreate] = []


class AccountUpdate(BaseModel):
    account_number: str | None = None
    custodian: str | None = None
    account_type: str | None = None
    account_value: Decimal | None = None


class OwnershipResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    member_id: uuid.UUID
    ownership_percentage: Decimal | None = None
    member_name: str | None = None


class AccountResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    household_id: uuid.UUID
    account_number: str | None = None
    custodian: str | None = None
    account_type: str | None = None
    account_value: Decimal | None = None
    ownerships: list[OwnershipResponse] = []
