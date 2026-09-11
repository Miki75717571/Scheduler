import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ShiftSlotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    period_id: uuid.UUID
    date: date
    shift_type_id: uuid.UUID
    required_staff: int
    min_staff: int
    max_staff: int
    is_closed: bool
    note: str | None


class ShiftSlotUpdate(BaseModel):
    required_staff: int | None = Field(default=None, ge=0)
    min_staff: int | None = Field(default=None, ge=0)
    max_staff: int | None = Field(default=None, ge=0)
    is_closed: bool | None = None
    note: str | None = None
