import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.types import UTCDateTime


class EmployeeScore(Base):
    """One versioned rating of one employee on one criterion
    (ARCHITECTURE.md ss3.4). Never UPDATEd - a change always INSERTs a new row
    with a new `effective_from`, so a composite computed for a past month
    stays explainable with that month's scores (CLAUDE.md "Scores"). Each row
    is itself one audit entry: who (`set_by_user_id`), what (`value`), when
    (`created_at`), and why (`note`) - see
    app/services/score_service.py.get_history for how consecutive rows are
    diffed into a "changed from X to Y" timeline.
    """

    __tablename__ = "employee_scores"
    __table_args__ = (
        CheckConstraint("value BETWEEN 1 AND 5", name="ck_employee_scores_value_range"),
        Index("ix_employee_scores_user_criterion", "user_id", "criterion_id", "effective_from"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    criterion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("score_criteria.id"), nullable=False
    )
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    set_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, server_default=func.now()
    )
