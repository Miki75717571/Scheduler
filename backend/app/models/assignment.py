import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, UniqueConstraint, false, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.types import StrEnumType, UTCDateTime


class AssignmentSource(enum.StrEnum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"


class Assignment(Base):
    """One person on one shift. `is_locked` is the manager pinning this so a
    future solver run (Phase 5) must not move it - respected here even though
    no solver exists yet, per ARCHITECTURE.md ss3.6.

    `modified_after_publish` is set whenever a mutation touches this row while
    the owning period is PUBLISHED, so the manager calendar can highlight
    what changed since staff last saw it without re-deriving that from
    AuditLog on every render. AuditLog itself remains the authoritative,
    complete record (including removals, which leave no row here to flag).
    """

    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint("shift_slot_id", "user_id", name="uq_assignments_slot_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shift_slot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("shift_slots.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    source: Mapped[AssignmentSource] = mapped_column(
        StrEnumType(AssignmentSource, 10), nullable=False, default=AssignmentSource.MANUAL
    )
    is_locked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    modified_after_publish: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
