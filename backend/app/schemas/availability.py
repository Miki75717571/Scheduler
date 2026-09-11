import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.availability import AvailabilityStatus, SubmissionStatus


class AvailabilityEntryWrite(BaseModel):
    shift_slot_id: uuid.UUID
    status: AvailabilityStatus
    note: str | None = None


class AvailabilityWriteRequest(BaseModel):
    entries: list[AvailabilityEntryWrite] = Field(default_factory=list)


class AvailabilityEntryRead(BaseModel):
    shift_slot_id: uuid.UUID
    status: AvailabilityStatus
    note: str | None = None


class RuleCheckResultRead(BaseModel):
    rule_code: str
    severity: str
    passed: bool
    message_key: str
    message_params: dict[str, Any]


class AvailabilitySubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    period_id: uuid.UUID
    status: SubmissionStatus
    submitted_at: datetime | None
    last_edited_at: datetime | None
    reopened_by_manager: bool


class AvailabilityDetailRead(BaseModel):
    submission: AvailabilitySubmissionRead
    entries: list[AvailabilityEntryRead]
    validation: list[RuleCheckResultRead]


class SubmissionTrackerEntry(BaseModel):
    user_id: uuid.UUID
    full_name: str
    employment_type: str | None
    status: SubmissionStatus
    submitted_at: datetime | None
    reopened_by_manager: bool
