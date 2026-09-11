import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.types import StrEnumType, UTCDateTime


class SubmissionStatus(enum.StrEnum):
    NOT_STARTED = "NOT_STARTED"
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"


class AvailabilityStatus(enum.StrEnum):
    UNAVAILABLE = "UNAVAILABLE"
    AVAILABLE = "AVAILABLE"
    PREFERRED = "PREFERRED"


class AvailabilitySubmission(Base):
    """One per (user, period). Rows are created eagerly (status=NOT_STARTED)
    for every active user when a period transitions to COLLECTING - see
    PeriodService._ensure_submissions_for_active_users - and lazily for
    anyone added afterward, so the manager tracker is a single query rather
    than a LEFT JOIN/anti-join over users.
    """

    __tablename__ = "availability_submissions"
    __table_args__ = (
        UniqueConstraint("user_id", "period_id", name="uq_availability_submissions_user_period"),
        CheckConstraint(
            "status IN ('NOT_STARTED','DRAFT','SUBMITTED')",
            name="ck_availability_submissions_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("schedule_periods.id"), nullable=False
    )
    status: Mapped[SubmissionStatus] = mapped_column(
        StrEnumType(SubmissionStatus, 20), nullable=False, default=SubmissionStatus.NOT_STARTED
    )
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_edited_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # Manager-only escape hatch: while True, this employee may edit past
    # LOCKED even though the period as a whole is frozen. Toggled by
    # POST/DELETE /periods/{id}/availability/{user_id}/reopen.
    reopened_by_manager: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )


class Availability(Base):
    """One per (submission, shift_slot). A row is only ever written for
    AVAILABLE/PREFERRED - setting a slot back to UNAVAILABLE deletes the row
    (see AvailabilityRepository) so "absent means UNAVAILABLE" stays true at
    the storage layer too, not just as an API convention.
    """

    __tablename__ = "availabilities"
    __table_args__ = (
        UniqueConstraint(
            "submission_id", "shift_slot_id", name="uq_availabilities_submission_slot"
        ),
        CheckConstraint(
            "status IN ('UNAVAILABLE','AVAILABLE','PREFERRED')", name="ck_availabilities_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("availability_submissions.id"), nullable=False
    )
    shift_slot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("shift_slots.id"), nullable=False
    )
    status: Mapped[AvailabilityStatus] = mapped_column(
        StrEnumType(AvailabilityStatus, 20), nullable=False
    )
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
