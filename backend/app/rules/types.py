"""Plain data types for rule evaluation - deliberately DB-free (mirrors the
scheduling/ purity pattern) so rule handlers stay unit-testable without a
session: app/services/availability_service.py does the ORM -> SlotContext
conversion, app/rules/availability_validator.py never touches app.models
instances directly.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.models.availability import AvailabilityStatus


@dataclass(frozen=True)
class SlotContext:
    shift_slot_id: uuid.UUID
    date: date
    shift_type_code: str
    status: AvailabilityStatus


@dataclass(frozen=True)
class RuleCheckResult:
    rule_code: str
    rule_type: str
    severity: str
    passed: bool
    message_key: str
    message_params: dict[str, Any]
