import uuid
from datetime import time as time_

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.types import StrEnumType
from app.rules.weekdays import Weekday


class ShiftTypeWeekdayOverride(Base):
    """A per-weekday override of one ShiftType's times/staffing (CLAUDE.md
    "per-weekday shift times"). ShiftType keeps its own start_time/end_time/
    staff triple as the fallback used for any active weekday that has no
    override row here - see app/services/shift_effective.py's
    `resolve_effective_config`, the only place that reads both and decides
    which wins. Employees/rules never see this table directly: they keep
    matching on ShiftType.code (e.g. "EVENING"), exactly as before - only the
    clock times and staffing levels vary per day.
    """

    __tablename__ = "shift_type_weekday_overrides"
    __table_args__ = (
        UniqueConstraint(
            "shift_type_id", "weekday", name="uq_shift_type_weekday_overrides_type_day"
        ),
        CheckConstraint("end_time > start_time", name="ck_shift_type_weekday_overrides_time_order"),
        CheckConstraint(
            "min_staff <= required_staff AND required_staff <= max_staff",
            name="ck_shift_type_weekday_overrides_staff_order",
        ),
        CheckConstraint(
            "weekday IN ('MON','TUE','WED','THU','FRI','SAT','SUN')",
            name="ck_shift_type_weekday_overrides_weekday",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shift_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("shift_types.id"), nullable=False
    )
    weekday: Mapped[Weekday] = mapped_column(StrEnumType(Weekday, 3), nullable=False)
    start_time: Mapped[time_] = mapped_column(Time, nullable=False)
    end_time: Mapped[time_] = mapped_column(Time, nullable=False)
    min_staff: Mapped[int] = mapped_column(Integer, nullable=False)
    required_staff: Mapped[int] = mapped_column(Integer, nullable=False)
    max_staff: Mapped[int] = mapped_column(Integer, nullable=False)
