import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.schedule_run import ScheduleRunStatus


class ScheduleRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    period_id: uuid.UUID
    status: ScheduleRunStatus
    algorithm_version: str
    params_snapshot: dict[str, Any]
    objective_value: float | None
    solve_time_ms: int | None
    solver_status: str | None
    stats: dict[str, Any] | None
    diagnostics: dict[str, Any] | None
    error_message: str | None
    pre_run_snapshot: list[dict[str, Any]] | None
    reverted_at: datetime | None
    reverted_by_user_id: uuid.UUID | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ScheduleRunCreate(BaseModel):
    # Overrides the default 30s cap (ARCHITECTURE.md ss4/CLAUDE.md "Running
    # it") for one run only - the live solver_weight_configs row is unaffected.
    time_limit_seconds: float | None = Field(default=None, gt=0, le=300)
