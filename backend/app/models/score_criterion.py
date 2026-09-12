import uuid
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Integer, Numeric, String, false
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class ScoreCriterion(Base):
    """Admin-managed rating axis (ARCHITECTURE.md ss3.4) - "customer service",
    "reliability", etc. The set of criteria and their weights must never be
    hard-coded elsewhere: app/seed.py only inserts a starting default set, and
    app/services/score_service.py computes the composite generically over
    whatever rows are active, so an admin can rename, add, or reweight them
    with no code change.

    `weight` is sa.Numeric (exact Decimal), never Float, because the sum of
    active weights must equal exactly 1.0 - see
    app/services/score_service.py's `_validate_active_weights_sum`.
    """

    __tablename__ = "score_criteria"
    __table_args__ = (
        CheckConstraint("scale_min < scale_max", name="ck_score_criteria_scale_order"),
        CheckConstraint("weight >= 0", name="ck_score_criteria_weight_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name_pl: Mapped[str] = mapped_column(String(150), nullable=False)
    name_en: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("0"))
    scale_min: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    scale_max: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
