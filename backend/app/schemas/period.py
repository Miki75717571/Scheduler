import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.schedule_period import PeriodState


class PeriodCreate(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    availability_opens_at: datetime | None = None
    availability_deadline: datetime | None = None


class PeriodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    year: int
    month: int
    state: PeriodState
    availability_opens_at: datetime | None
    availability_deadline: datetime | None
    published_at: datetime | None
    published_by_user_id: uuid.UUID | None
    created_at: datetime


class PeriodStateUpdate(BaseModel):
    state: PeriodState
    # Only meaningful for a GENERATED -> PUBLISHED transition: publishing is
    # normally refused while ERROR-severity schedule violations exist
    # (see app/api/v1/periods.py); this explicitly acknowledges and overrides
    # that block, which gets recorded in AuditLog.
    override_violations: bool = False
