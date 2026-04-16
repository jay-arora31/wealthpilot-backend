import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ConflictResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    household_id: uuid.UUID
    field_name: str
    existing_value: str | None = None
    incoming_value: str | None = None
    source_quote: str | None = None
    source: str
    status: str
    created_at: datetime
    resolved_at: datetime | None = None


class ConflictResolveRequest(BaseModel):
    action: Literal["accept", "reject"]
