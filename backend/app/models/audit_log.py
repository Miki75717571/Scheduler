import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.types import UTCDateTime


class AuditLog(Base):
    """Who did what, when - ARCHITECTURE.md ss3.6. `period_id` is a
    denormalized convenience (every entity this phase logs belongs to exactly
    one period) so "what changed since publish" is a single indexed query
    (`period_id = ? AND at > published_at`) instead of a join through
    Assignment/ShiftSlot for rows whose Assignment may already be deleted.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_period_id_at", "period_id", "at"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("schedule_periods.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, server_default=func.now())
