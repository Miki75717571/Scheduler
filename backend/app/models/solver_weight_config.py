import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.types import UTCDateTime


class SolverWeightConfig(Base):
    """The live, admin-tunable objective coefficients (ARCHITECTURE.md ss4.1),
    mirroring app/scheduling/domain.py's SolverWeights field-for-field.
    CLAUDE.md: "Weights live in a database config table, not in code, so I
    can tune them without a deploy." A single row (app/repositories's
    `get_or_create_default` enforces this) rather than a versioned table like
    EmployeeScore - the weights actually used for any given run are already
    frozen forever onto that run's `params_snapshot`
    (app/models/schedule_run.py), so this row only ever needs to answer "what
    would a new run use right now."
    """

    __tablename__ = "solver_weight_configs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    understaffing: Mapped[int] = mapped_column(Integer, nullable=False, default=10000)
    contract_min_shortfall: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    denied_preference: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    fairness_spread: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    unpopular_shift_spread: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    score_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    preference_debt: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, server_default=func.now()
    )
