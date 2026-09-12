"""The SCHEDULE-phase rule engine (ARCHITECTURE.md ss3.5). Deliberately
separate from the (future) CP-SAT solver: "the solver tells you what it
*intended*; the validator tells you what is *true* right now." Pure - no DB
session, no ORM query - so it is fixture-testable exactly like
app/rules/availability_validator.py (see tests/unit/test_schedule_validator.py).

Two kinds of checks live here:

1. Rule-driven handlers (ONE_SHIFT_PER_DAY, MIN_REST_HOURS, MAX_CONSECUTIVE_DAYS,
   MIN/MAX_SHIFTS_PER_MONTH, MAX_WEEKEND_SHIFTS) - registered via @rule_handler,
   evaluated per employee against whatever Rule rows apply to them
   (app/repositories/rule_repository.py's GLOBAL/EMPLOYMENT_TYPE/USER scoping).
   New types get a handler here, never an `if rule.type == ...` in a service
   (CLAUDE.md "Rules as data").

2. Always-on structural checks that aren't configurable Rule rows at all:
   understaffing (derived directly from ShiftSlot.required_staff/min_staff,
   exactly like the solver's own soft-understaffing modelling in
   ARCHITECTURE.md ss4.1) and "assigned despite declared/defaulted
   UNAVAILABLE" (a cross-check against Availability, always advisory -
   "the system advises, it does not forbid").

Every Rule.severity (HARD/SOFT) maps onto ScheduleViolation.severity as
ERROR/WARNING respectively - the one place that mapping happens.
"""

import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.models.rule import Rule, RuleSeverity, RuleType
from app.rules.types import AssignedShift, ScheduleViolation, SlotStaffing, UserScheduleContext

Handler = Callable[[Rule, UserScheduleContext], list[ScheduleViolation]]

_REGISTRY: dict[RuleType, Handler] = {}


def rule_handler(rule_type: RuleType) -> Callable[[Handler], Handler]:
    def _register(fn: Handler) -> Handler:
        _REGISTRY[rule_type] = fn
        return fn

    return _register


def _severity(rule: Rule) -> str:
    return "ERROR" if rule.severity == RuleSeverity.HARD else "WARNING"


def _sorted_shifts(context: UserScheduleContext) -> list[AssignedShift]:
    return sorted(context.assigned_shifts, key=lambda s: (s.date, s.start_time))


@rule_handler(RuleType.ONE_SHIFT_PER_DAY)
def _check_one_shift_per_day(rule: Rule, context: UserScheduleContext) -> list[ScheduleViolation]:
    by_date: dict[Any, list[AssignedShift]] = defaultdict(list)
    for shift in context.assigned_shifts:
        by_date[shift.date].append(shift)

    violations = []
    for day, shifts in sorted(by_date.items()):
        if len(shifts) <= 1:
            continue
        violations.append(
            ScheduleViolation(
                severity=_severity(rule),
                rule_code=rule.code,
                rule_type=rule.type.value,
                message_key="rules.ONE_SHIFT_PER_DAY",
                message_params={
                    "date": day.isoformat(),
                    "count": len(shifts),
                    "shift_slot_ids": [str(s.shift_slot_id) for s in shifts],
                },
                shift_slot_id=None,
                user_id=context.user_id,
            )
        )
    return violations


@rule_handler(RuleType.MIN_REST_HOURS)
def _check_min_rest_hours(rule: Rule, context: UserScheduleContext) -> list[ScheduleViolation]:
    required_hours = int(rule.params["h"])
    shifts = _sorted_shifts(context)

    violations = []
    for previous, current in zip(shifts, shifts[1:], strict=False):
        rest = datetime.combine(current.date, current.start_time) - datetime.combine(
            previous.date, previous.end_time
        )
        rest_hours = rest.total_seconds() / 3600
        if rest_hours < required_hours:
            violations.append(
                ScheduleViolation(
                    severity=_severity(rule),
                    rule_code=rule.code,
                    rule_type=rule.type.value,
                    message_key="rules.MIN_REST_HOURS",
                    message_params={
                        "required": required_hours,
                        "actual": round(rest_hours, 1),
                        "from_shift_slot_id": str(previous.shift_slot_id),
                        "to_shift_slot_id": str(current.shift_slot_id),
                    },
                    shift_slot_id=current.shift_slot_id,
                    user_id=context.user_id,
                )
            )
    return violations


@rule_handler(RuleType.MAX_CONSECUTIVE_DAYS)
def _check_max_consecutive_days(
    rule: Rule, context: UserScheduleContext
) -> list[ScheduleViolation]:
    allowed = int(rule.params["n"])
    dates = sorted({s.date for s in context.assigned_shifts})

    violations = []
    run_start = 0
    for i in range(1, len(dates) + 1):
        broke_run = i == len(dates) or (dates[i] - dates[i - 1]).days > 1
        if not broke_run:
            continue
        run_length = i - run_start
        if run_length > allowed:
            violations.append(
                ScheduleViolation(
                    severity=_severity(rule),
                    rule_code=rule.code,
                    rule_type=rule.type.value,
                    message_key="rules.MAX_CONSECUTIVE_DAYS",
                    message_params={
                        "allowed": allowed,
                        "actual": run_length,
                        "start": dates[run_start].isoformat(),
                        "end": dates[i - 1].isoformat(),
                    },
                    shift_slot_id=None,
                    user_id=context.user_id,
                )
            )
        run_start = i
    return violations


@rule_handler(RuleType.MIN_SHIFTS_PER_MONTH)
def _check_min_shifts_per_month(
    rule: Rule, context: UserScheduleContext
) -> list[ScheduleViolation]:
    required = (
        context.contract_min_shifts
        if context.contract_min_shifts is not None
        else int(rule.params["n"])
    )
    actual = len(context.assigned_shifts)
    if actual >= required:
        return []
    return [
        ScheduleViolation(
            severity=_severity(rule),
            rule_code=rule.code,
            rule_type=rule.type.value,
            message_key="rules.MIN_SHIFTS_PER_MONTH",
            message_params={"required": required, "actual": actual},
            shift_slot_id=None,
            user_id=context.user_id,
        )
    ]


@rule_handler(RuleType.MAX_SHIFTS_PER_MONTH)
def _check_max_shifts_per_month(
    rule: Rule, context: UserScheduleContext
) -> list[ScheduleViolation]:
    allowed = (
        context.contract_max_shifts
        if context.contract_max_shifts is not None
        else int(rule.params["n"])
    )
    actual = len(context.assigned_shifts)
    if actual <= allowed:
        return []
    return [
        ScheduleViolation(
            severity=_severity(rule),
            rule_code=rule.code,
            rule_type=rule.type.value,
            message_key="rules.MAX_SHIFTS_PER_MONTH",
            message_params={"allowed": allowed, "actual": actual},
            shift_slot_id=None,
            user_id=context.user_id,
        )
    ]


@rule_handler(RuleType.MAX_WEEKEND_SHIFTS)
def _check_max_weekend_shifts(rule: Rule, context: UserScheduleContext) -> list[ScheduleViolation]:
    allowed = int(rule.params["n"])
    actual = sum(1 for s in context.assigned_shifts if s.is_weekend)
    if actual <= allowed:
        return []
    return [
        ScheduleViolation(
            severity=_severity(rule),
            rule_code=rule.code,
            rule_type=rule.type.value,
            message_key="rules.MAX_WEEKEND_SHIFTS",
            message_params={"allowed": allowed, "actual": actual},
            shift_slot_id=None,
            user_id=context.user_id,
        )
    ]


def evaluate_schedule_rules(
    rules: list[Rule], context: UserScheduleContext
) -> list[ScheduleViolation]:
    violations: list[ScheduleViolation] = []
    for rule in rules:
        handler = _REGISTRY.get(rule.type)
        if handler is None:
            continue
        violations.extend(handler(rule, context))
    return violations


def check_understaffing(slot_staffing: list[SlotStaffing]) -> list[ScheduleViolation]:
    """Always on, never a Rule row - mirrors the solver's own soft-understaffing
    modelling (ARCHITECTURE.md ss4.1): below required_staff is a WARNING
    (legal but thin), below min_staff is an ERROR (the day cannot run safely).
    """
    violations = []
    for slot in slot_staffing:
        if slot.is_closed:
            continue
        assigned = len(slot.assigned_user_ids)
        if assigned < slot.min_staff:
            violations.append(
                ScheduleViolation(
                    severity="ERROR",
                    rule_code="UNDERSTAFFING",
                    rule_type="UNDERSTAFFING",
                    message_key="schedule.understaffed_below_minimum",
                    message_params={
                        "assigned": assigned,
                        "min_staff": slot.min_staff,
                        "required_staff": slot.required_staff,
                    },
                    shift_slot_id=slot.shift_slot_id,
                    user_id=None,
                )
            )
        elif assigned < slot.required_staff:
            violations.append(
                ScheduleViolation(
                    severity="WARNING",
                    rule_code="UNDERSTAFFING",
                    rule_type="UNDERSTAFFING",
                    message_key="schedule.understaffed_below_required",
                    message_params={"assigned": assigned, "required_staff": slot.required_staff},
                    shift_slot_id=slot.shift_slot_id,
                    user_id=None,
                )
            )
    return violations


def check_unavailable_assignments(
    assigned_shifts_by_user: dict[uuid.UUID, tuple[AssignedShift, ...]],
    declared_available: set[tuple[uuid.UUID, uuid.UUID]],
) -> list[ScheduleViolation]:
    """Always on, never a Rule row. `declared_available` holds (user_id,
    shift_slot_id) pairs where the employee marked AVAILABLE or PREFERRED;
    absence means UNAVAILABLE (ARCHITECTURE.md ss3.3's safe default) - so an
    assignment not in this set is flagged whether the employee explicitly
    said no or simply never filled the slot in. This is advisory only: "the
    system advises, it does not forbid" - real exceptions (someone changes
    their mind, someone covers a sick colleague) are exactly what this
    validator must allow.
    """
    violations = []
    for user_id, shifts in assigned_shifts_by_user.items():
        for shift in shifts:
            if (user_id, shift.shift_slot_id) in declared_available:
                continue
            violations.append(
                ScheduleViolation(
                    severity="WARNING",
                    rule_code="AVAILABILITY_MISMATCH",
                    rule_type="AVAILABILITY_MISMATCH",
                    message_key="schedule.assigned_despite_unavailable",
                    message_params={},
                    shift_slot_id=shift.shift_slot_id,
                    user_id=user_id,
                )
            )
    return violations
