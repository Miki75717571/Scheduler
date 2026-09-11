import uuid
from datetime import date as date_

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class ShiftSlot(Base):
    """One row per (period, date, shift type) - generated when the period is
    created (see app/services/period_service.py), not computed on the fly, so
    a manager can edit staffing per day or close a slot for a holiday.
    """

    __tablename__ = "shift_slots"
    __table_args__ = (
        UniqueConstraint(
            "period_id", "date", "shift_type_id", name="uq_shift_slots_period_date_type"
        ),
        CheckConstraint(
            "min_staff <= required_staff AND required_staff <= max_staff",
            name="ck_shift_slots_staff_order",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("schedule_periods.id"), nullable=False
    )
    # Local date, never a timestamp - see CLAUDE.md "Dates/times".
    date: Mapped[date_] = mapped_column(Date, nullable=False)
    shift_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("shift_types.id"), nullable=False
    )
    required_staff: Mapped[int] = mapped_column(Integer, nullable=False)
    min_staff: Mapped[int] = mapped_column(Integer, nullable=False)
    max_staff: Mapped[int] = mapped_column(Integer, nullable=False)
    is_closed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
