import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class EmployeeScoreCreate(BaseModel):
    criterion_id: uuid.UUID
    value: int = Field(ge=1, le=5)
    # None -> today, set in app/services/score_service.py so "today" is
    # resolved once, server-side, rather than trusting the client's clock.
    effective_from: date | None = None
    note: str | None = None


class ScoreEntryRead(BaseModel):
    """One criterion's currently-effective value for one employee."""

    criterion_id: uuid.UUID
    value: int
    effective_from: date
    set_by_user_id: uuid.UUID
    note: str | None


class ScoreGridRow(BaseModel):
    """One row of the manager scoring grid: an employee, their
    currently-effective value per active criterion, and the composite."""

    user_id: uuid.UUID
    full_name: str
    entries: list[ScoreEntryRead]
    composite: float | None


class ScoreHistoryEntryRead(BaseModel):
    """One past change, enriched for display: the criterion's name and who
    set it, plus the value it replaced (None for a criterion's first-ever
    score) - computed by diffing consecutive EmployeeScore rows, since no
    row is ever updated in place (see app/models/employee_score.py).
    """

    id: uuid.UUID
    criterion_id: uuid.UUID
    criterion_code: str
    criterion_name_pl: str
    criterion_name_en: str
    value: int
    previous_value: int | None
    effective_from: date
    set_by_user_id: uuid.UUID
    set_by_full_name: str
    note: str | None
    created_at: datetime
