import uuid
from datetime import date, time

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
    # Effective for this specific date (app/services/shift_effective.py) -
    # never read ShiftType.start_time/end_time directly once a slot is in
    # hand, since Mon-Thu/Friday/weekend can each have their own times under
    # the same shift_type_id (CLAUDE.md "per-weekday shift times").
    start_time: time
    end_time: time


class ShiftSlotUpdate(BaseModel):
    required_staff: int | None = Field(default=None, ge=0)
    min_staff: int | None = Field(default=None, ge=0)
    max_staff: int | None = Field(default=None, ge=0)
    is_closed: bool | None = None
    note: str | None = None
