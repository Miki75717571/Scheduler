"""Pure schedule-validator tests - hand-built fixtures, no DB, mirroring
tests/unit/test_availability_validator.py. These are the highest-value tests
in Phase 3: CLAUDE.md ranks solver/validator invariants first among testing
priorities.
"""

import uuid
from datetime import date, time
from typing import Any

from app.models.rule import Rule, RulePhase, RuleScope, RuleSeverity, RuleType
from app.rules.schedule_validator import (
    check_unavailable_assignments,
    check_understaffing,
    evaluate_schedule_rules,
)
from app.rules.types import AssignedShift, ScheduleViolation, SlotStaffing, UserScheduleContext

MORNING = (time(7, 0), time(15, 0))
EVENING = (time(15, 0), time(23, 0))

MONDAY = date(2026, 10, 5)
TUESDAY = date(2026, 10, 6)
WEDNESDAY = date(2026, 10, 7)
SATURDAY = date(2026, 10, 10)
SUNDAY = date(2026, 10, 11)


def _rule(
    *,
    type_: RuleType,
    params: dict[str, Any],
    code: str = "r1",
    severity: RuleSeverity = RuleSeverity.HARD,
    scope: RuleScope = RuleScope.GLOBAL,
    scope_ref: str | None = None,
) -> Rule:
    return Rule(
        code=code,
        name_pl=code,
        name_en=code,
        type=type_,
        scope=scope,
        scope_ref=scope_ref,
        params=params,
        severity=severity,
        phase=RulePhase.SCHEDULE,
        is_active=True,
    )


def _shift(d: date, times: tuple[time, time], *, is_weekend: bool = False) -> AssignedShift:
    return AssignedShift(
        shift_slot_id=uuid.uuid4(),
        date=d,
        shift_type_code="MORNING" if times == MORNING else "EVENING",
        start_time=times[0],
        end_time=times[1],
        is_weekend=is_weekend,
    )


def _context(
    shifts: list[AssignedShift],
    *,
    user_id: uuid.UUID | None = None,
    contract_min_shifts: int | None = None,
    contract_max_shifts: int | None = None,
) -> UserScheduleContext:
    return UserScheduleContext(
        user_id=user_id or uuid.uuid4(),
        assigned_shifts=tuple(shifts),
        contract_min_shifts=contract_min_shifts,
        contract_max_shifts=contract_max_shifts,
    )


def _only(violations: list[ScheduleViolation]) -> ScheduleViolation:
    assert len(violations) == 1, violations
    return violations[0]


# --- ONE_SHIFT_PER_DAY --------------------------------------------------


def test_one_shift_per_day_passes_with_distinct_days() -> None:
    rule = _rule(type_=RuleType.ONE_SHIFT_PER_DAY, params={})
    context = _context([_shift(MONDAY, MORNING), _shift(TUESDAY, EVENING)])

    assert evaluate_schedule_rules([rule], context) == []


def test_one_shift_per_day_flags_double_booking_as_error() -> None:
    rule = _rule(type_=RuleType.ONE_SHIFT_PER_DAY, params={}, severity=RuleSeverity.HARD)
    context = _context([_shift(MONDAY, MORNING), _shift(MONDAY, EVENING)])

    violation = _only(evaluate_schedule_rules([rule], context))
    assert violation.severity == "ERROR"
    assert violation.message_params["count"] == 2


# --- MIN_REST_HOURS ------------------------------------------------------


def test_min_rest_hours_passes_with_enough_gap() -> None:
    rule = _rule(type_=RuleType.MIN_REST_HOURS, params={"h": 11})
    # Evening Monday (ends 23:00) -> morning Wednesday (starts 07:00): fine.
    context = _context([_shift(MONDAY, EVENING), _shift(WEDNESDAY, MORNING)])

    assert evaluate_schedule_rules([rule], context) == []


def test_min_rest_hours_flags_evening_then_next_morning() -> None:
    rule = _rule(type_=RuleType.MIN_REST_HOURS, params={"h": 11}, severity=RuleSeverity.HARD)
    # Evening Monday (ends 23:00) -> morning Tuesday (starts 07:00): 8h rest.
    context = _context([_shift(MONDAY, EVENING), _shift(TUESDAY, MORNING)])

    violation = _only(evaluate_schedule_rules([rule], context))
    assert violation.severity == "ERROR"
    assert violation.message_params == {
        "required": 11,
        "actual": 8.0,
        "from_shift_slot_id": str(context.assigned_shifts[0].shift_slot_id),
        "to_shift_slot_id": str(context.assigned_shifts[1].shift_slot_id),
    }


# --- MAX_CONSECUTIVE_DAYS -------------------------------------------------


def test_max_consecutive_days_passes_within_limit() -> None:
    rule = _rule(type_=RuleType.MAX_CONSECUTIVE_DAYS, params={"n": 5}, severity=RuleSeverity.SOFT)
    days = [date(2026, 10, d) for d in range(5, 9)]  # 4 consecutive days
    context = _context([_shift(d, MORNING) for d in days])

    assert evaluate_schedule_rules([rule], context) == []


def test_max_consecutive_days_flags_a_run_beyond_the_limit() -> None:
    rule = _rule(type_=RuleType.MAX_CONSECUTIVE_DAYS, params={"n": 3}, severity=RuleSeverity.SOFT)
    days = [date(2026, 10, d) for d in range(5, 10)]  # 5 consecutive days
    context = _context([_shift(d, MORNING) for d in days])

    violation = _only(evaluate_schedule_rules([rule], context))
    assert violation.severity == "WARNING"
    assert violation.message_params["actual"] == 5


# --- MIN/MAX_SHIFTS_PER_MONTH (with contract overrides) -------------------


def test_min_shifts_per_month_uses_global_default_when_no_override() -> None:
    rule = _rule(type_=RuleType.MIN_SHIFTS_PER_MONTH, params={"n": 5}, severity=RuleSeverity.SOFT)
    context = _context([_shift(MONDAY, MORNING), _shift(TUESDAY, MORNING)])

    violation = _only(evaluate_schedule_rules([rule], context))
    assert violation.message_params == {"required": 5, "actual": 2}


def test_min_shifts_per_month_uses_personal_contract_override() -> None:
    """actual=6 clears the global default (5) but not this employee's
    personal contract_min_shifts override (10) - proves the override, not
    the rule's own param, wins.
    """
    rule = _rule(type_=RuleType.MIN_SHIFTS_PER_MONTH, params={"n": 5}, severity=RuleSeverity.SOFT)
    shifts = [_shift(date(2026, 10, d), MORNING) for d in (1, 3, 5, 7, 9, 11)]
    context = _context(shifts, contract_min_shifts=10)

    violation = _only(evaluate_schedule_rules([rule], context))
    assert violation.message_params == {"required": 10, "actual": 6}


def test_max_shifts_per_month_flags_exceeding_contract_ceiling() -> None:
    rule = _rule(type_=RuleType.MAX_SHIFTS_PER_MONTH, params={"n": 20}, severity=RuleSeverity.SOFT)
    shifts = [_shift(date(2026, 10, d), MORNING) for d in range(1, 5)]
    context = _context(shifts, contract_max_shifts=3)

    violation = _only(evaluate_schedule_rules([rule], context))
    assert violation.message_params == {"allowed": 3, "actual": 4}


# --- MAX_WEEKEND_SHIFTS ----------------------------------------------------


def test_max_weekend_shifts_counts_only_weekend_flagged_shifts() -> None:
    rule = _rule(type_=RuleType.MAX_WEEKEND_SHIFTS, params={"n": 1}, severity=RuleSeverity.SOFT)
    context = _context(
        [
            _shift(SATURDAY, MORNING, is_weekend=True),
            _shift(SUNDAY, MORNING, is_weekend=True),
            _shift(MONDAY, MORNING, is_weekend=False),
        ]
    )

    violation = _only(evaluate_schedule_rules([rule], context))
    assert violation.message_params == {"allowed": 1, "actual": 2}


# --- always-on: understaffing ----------------------------------------------


def test_understaffing_below_required_is_a_warning() -> None:
    slot = SlotStaffing(
        shift_slot_id=uuid.uuid4(),
        date=MONDAY,
        shift_type_code="EVENING",
        required_staff=3,
        min_staff=2,
        max_staff=4,
        is_closed=False,
        assigned_user_ids=(uuid.uuid4(), uuid.uuid4()),  # 2 of 3 required, >= min
    )

    violation = _only(check_understaffing([slot]))
    assert violation.severity == "WARNING"
    assert violation.message_key == "schedule.understaffed_below_required"


def test_understaffing_below_minimum_is_an_error() -> None:
    slot = SlotStaffing(
        shift_slot_id=uuid.uuid4(),
        date=MONDAY,
        shift_type_code="EVENING",
        required_staff=3,
        min_staff=2,
        max_staff=4,
        is_closed=False,
        assigned_user_ids=(uuid.uuid4(),),  # 1 < min_staff=2
    )

    violation = _only(check_understaffing([slot]))
    assert violation.severity == "ERROR"
    assert violation.message_key == "schedule.understaffed_below_minimum"


def test_understaffing_ignores_closed_slots() -> None:
    slot = SlotStaffing(
        shift_slot_id=uuid.uuid4(),
        date=MONDAY,
        shift_type_code="EVENING",
        required_staff=3,
        min_staff=2,
        max_staff=4,
        is_closed=True,
        assigned_user_ids=(),
    )

    assert check_understaffing([slot]) == []


def test_fully_staffed_slot_has_no_violation() -> None:
    slot = SlotStaffing(
        shift_slot_id=uuid.uuid4(),
        date=MONDAY,
        shift_type_code="EVENING",
        required_staff=2,
        min_staff=1,
        max_staff=3,
        is_closed=False,
        assigned_user_ids=(uuid.uuid4(), uuid.uuid4()),
    )

    assert check_understaffing([slot]) == []


# --- always-on: assigned despite unavailable -------------------------------


def test_assignment_matching_declared_availability_is_not_flagged() -> None:
    user_id = uuid.uuid4()
    slot_id = uuid.uuid4()
    shift = AssignedShift(
        shift_slot_id=slot_id,
        date=MONDAY,
        shift_type_code="MORNING",
        start_time=MORNING[0],
        end_time=MORNING[1],
        is_weekend=False,
    )

    violations = check_unavailable_assignments(
        {user_id: (shift,)}, declared_available={(user_id, slot_id)}
    )

    assert violations == []


def test_assignment_without_declared_availability_is_a_warning() -> None:
    """Covers both explicit UNAVAILABLE and simply never having filled the
    slot in - both are represented the same way (absence from
    declared_available), matching ARCHITECTURE.md's "silence means
    unavailable" default.
    """
    user_id = uuid.uuid4()
    slot_id = uuid.uuid4()
    shift = AssignedShift(
        shift_slot_id=slot_id,
        date=MONDAY,
        shift_type_code="MORNING",
        start_time=MORNING[0],
        end_time=MORNING[1],
        is_weekend=False,
    )

    violations = check_unavailable_assignments({user_id: (shift,)}, declared_available=set())

    violation = _only(violations)
    assert violation.severity == "WARNING"
    assert violation.message_key == "schedule.assigned_despite_unavailable"
    assert violation.user_id == user_id
    assert violation.shift_slot_id == slot_id


def test_evaluate_skips_unhandled_rule_types_gracefully() -> None:
    from unittest.mock import MagicMock

    unhandled = MagicMock(spec=Rule)
    unhandled.type = "SOME_FUTURE_TYPE"
    unhandled.code = str(uuid.uuid4())

    assert evaluate_schedule_rules([unhandled], _context([])) == []
