import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.types import StrEnumType, UTCDateTime


class PeriodState(enum.StrEnum):
    DRAFT = "DRAFT"
    COLLECTING = "COLLECTING"
    LOCKED = "LOCKED"
    GENERATED = "GENERATED"
    PUBLISHED = "PUBLISHED"


class SchedulePeriod(Base):
    __tablename__ = "schedule_periods"
    __table_args__ = (
        UniqueConstraint("year", "month", name="uq_schedule_periods_year_month"),
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_schedule_periods_month"),
        CheckConstraint(
            "state IN ('DRAFT','COLLECTING','LOCKED','GENERATED','PUBLISHED')",
            name="ck_schedule_periods_state",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[PeriodState] = mapped_column(
        StrEnumType(PeriodState, 20), nullable=False, default=PeriodState.DRAFT
    )
    availability_opens_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    availability_deadline: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    published_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, server_default=func.now()
    )
