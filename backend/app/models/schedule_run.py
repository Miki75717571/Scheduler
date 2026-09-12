import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.types import StrEnumType, UTCDateTime


class ScheduleRunStatus(enum.StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class ScheduleRun(Base):
    """One invocation of the CP-SAT solver (ARCHITECTURE.md ss3.6, ss4).
    Created PENDING by app/services/solver_service.py.create_run inside the
    request/response cycle (cheap: just an INSERT), then solved by a
    background task - never inside a request handler, since CP-SAT can take
    up to `time_limit_seconds` (CLAUDE.md "Running it").

    `params_snapshot` freezes the exact weights/time-limit/seed used, taken
    at creation time from the live `solver_weight_configs` row - so a run
    stays explainable even if an admin retunes the weights five minutes
    later. `stats`/`diagnostics` mirror app/scheduling/domain.py's
    SolverStats/Diagnostics as plain JSON (see solver_service.py's
    `_stats_to_json`/`_diagnostics_to_json`).
    """

    __tablename__ = "schedule_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCESS','FAILED')", name="ck_schedule_runs_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("schedule_periods.id"), nullable=False
    )
    status: Mapped[ScheduleRunStatus] = mapped_column(
        StrEnumType(ScheduleRunStatus, 10), nullable=False, default=ScheduleRunStatus.PENDING
    )
    algorithm_version: Mapped[str] = mapped_column(String(40), nullable=False)
    params_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    objective_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    solve_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # OPTIMAL | FEASIBLE | INFEASIBLE_FALLBACK | NO_EMPLOYEES | NO_SLOTS -
    # app/scheduling/domain.py's SolverOutput.status, not this row's own
    # PENDING/RUNNING/SUCCESS/FAILED lifecycle above.
    solver_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    stats: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    diagnostics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
