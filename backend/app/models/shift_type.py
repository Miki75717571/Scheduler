import uuid
from datetime import time as time_

from sqlalchemy import Boolean, CheckConstraint, Integer, String, Time, true
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class ShiftType(Base):
    """Configurable, not hard-coded: admins add/edit rows (see
    app/api/v1/shift_types.py) rather than the app special-casing shift
    names. `active_weekdays` is the bitmask from app/rules/weekdays.py -
    MIDDAY being Sat+Sun-only is data (96), not an `if weekend` in code.
    """

    __tablename__ = "shift_types"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_shift_types_time_order"),
        CheckConstraint(
            "active_weekdays > 0 AND active_weekdays <= 127",
            name="ck_shift_types_active_weekdays",
        ),
        CheckConstraint(
            "default_min_staff <= default_required_staff"
            " AND default_required_staff <= default_max_staff",
            name="ck_shift_types_staff_order",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name_pl: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    # Local wall-clock times, never a timestamp - see CLAUDE.md "Dates/times".
    start_time: Mapped[time_] = mapped_column(Time, nullable=False)
    end_time: Mapped[time_] = mapped_column(Time, nullable=False)
    color_hex: Mapped[str] = mapped_column(
        String(7), nullable=False, default="#64748b", server_default="#64748b"
    )
    active_weekdays: Mapped[int] = mapped_column(Integer, nullable=False)
    default_required_staff: Mapped[int] = mapped_column(Integer, nullable=False)
    default_min_staff: Mapped[int] = mapped_column(Integer, nullable=False)
    default_max_staff: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
