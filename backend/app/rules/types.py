"""Plain data types for rule evaluation - deliberately DB-free (mirrors the
scheduling/ purity pattern) so rule handlers stay unit-testable without a
session: app/services/availability_service.py does the ORM -> SlotContext
conversion, app/rules/availability_validator.py never touches app.models
instances directly.
"""

import uuid
from dataclasses import dataclass
from datetime import date, time
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


@dataclass(frozen=True)
class AssignedShift:
    """One employee's assignment to one shift, with just enough denormalized
    ShiftSlot/ShiftType data (date, times, weekend-ness) for schedule_validator
    to reason about it without touching the ORM.
    """

    shift_slot_id: uuid.UUID
    date: date
    shift_type_code: str
    start_time: time
    end_time: time
    is_weekend: bool


@dataclass(frozen=True)
class UserScheduleContext:
    """One employee's full picture for the SCHEDULE-phase rule handlers:
    their assignments for the period (sorted by date, start_time) plus their
    contract shift-count overrides (ARCHITECTURE.md ss3.1's nullable
    per-user overrides of the global MIN/MAX_SHIFTS_PER_MONTH rule params).
    """

    user_id: uuid.UUID
    assigned_shifts: tuple[AssignedShift, ...]
    contract_min_shifts: int | None
    contract_max_shifts: int | None


@dataclass(frozen=True)
class SlotStaffing:
    shift_slot_id: uuid.UUID
    date: date
    shift_type_code: str
    required_staff: int
    min_staff: int
    max_staff: int
    is_closed: bool
    assigned_user_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class ScheduleViolation:
    severity: str  # ERROR | WARNING
    rule_code: str
    rule_type: str
    message_key: str
    message_params: dict[str, Any]
    shift_slot_id: uuid.UUID | None
    user_id: uuid.UUID | None
