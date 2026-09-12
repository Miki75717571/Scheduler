import enum
import uuid
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, Integer, String, true
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.types import StrEnumType


class RuleType(enum.StrEnum):
    """Availability-phase and schedule-phase types (ARCHITECTURE.md ss3.5).
    Adding one means a new handler in app/rules/availability_validator.py or
    app/rules/schedule_validator.py plus widening the ck_rules_type CHECK
    constraint via migration - never an inline `if`.
    """

    MIN_AVAILABILITY_COUNT = "MIN_AVAILABILITY_COUNT"
    MIN_AVAILABILITY_IN_SET = "MIN_AVAILABILITY_IN_SET"
    MIN_AVAILABILITY_WEEKEND = "MIN_AVAILABILITY_WEEKEND"
    ONE_SHIFT_PER_DAY = "ONE_SHIFT_PER_DAY"
    MIN_REST_HOURS = "MIN_REST_HOURS"
    MAX_CONSECUTIVE_DAYS = "MAX_CONSECUTIVE_DAYS"
    MIN_SHIFTS_PER_MONTH = "MIN_SHIFTS_PER_MONTH"
    MAX_SHIFTS_PER_MONTH = "MAX_SHIFTS_PER_MONTH"
    MAX_WEEKEND_SHIFTS = "MAX_WEEKEND_SHIFTS"


class RuleScope(enum.StrEnum):
    GLOBAL = "GLOBAL"
    EMPLOYMENT_TYPE = "EMPLOYMENT_TYPE"
    USER = "USER"


class RuleSeverity(enum.StrEnum):
    HARD = "HARD"
    SOFT = "SOFT"


class RulePhase(enum.StrEnum):
    AVAILABILITY = "AVAILABILITY"
    SCHEDULE = "SCHEDULE"
    BOTH = "BOTH"


class Rule(Base):
    __tablename__ = "rules"
    __table_args__ = (
        CheckConstraint(
            "type IN ('MIN_AVAILABILITY_COUNT','MIN_AVAILABILITY_IN_SET',"
            "'MIN_AVAILABILITY_WEEKEND','ONE_SHIFT_PER_DAY','MIN_REST_HOURS',"
            "'MAX_CONSECUTIVE_DAYS','MIN_SHIFTS_PER_MONTH','MAX_SHIFTS_PER_MONTH',"
            "'MAX_WEEKEND_SHIFTS')",
            name="ck_rules_type",
        ),
        CheckConstraint("scope IN ('GLOBAL','EMPLOYMENT_TYPE','USER')", name="ck_rules_scope"),
        CheckConstraint("severity IN ('HARD','SOFT')", name="ck_rules_severity"),
        CheckConstraint("phase IN ('AVAILABILITY','SCHEDULE','BOTH')", name="ck_rules_phase"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name_pl: Mapped[str] = mapped_column(String(150), nullable=False)
    name_en: Mapped[str] = mapped_column(String(150), nullable=False)
    type: Mapped[RuleType] = mapped_column(StrEnumType(RuleType, 40), nullable=False)
    scope: Mapped[RuleScope] = mapped_column(
        StrEnumType(RuleScope, 20), nullable=False, default=RuleScope.GLOBAL
    )
    # Nullable-by-scope: holds an EmploymentType value when scope=EMPLOYMENT_TYPE,
    # a user id (str) when scope=USER, unused when scope=GLOBAL. Plain String
    # rather than two separate nullable FK columns - scope says how to read it.
    scope_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    severity: Mapped[RuleSeverity] = mapped_column(
        StrEnumType(RuleSeverity, 10), nullable=False, default=RuleSeverity.HARD
    )
    weight: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phase: Mapped[RulePhase] = mapped_column(StrEnumType(RulePhase, 20), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
