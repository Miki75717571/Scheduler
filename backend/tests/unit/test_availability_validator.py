"""Pure rule-logic tests - no DB, mirroring the priority CLAUDE.md gives
solver/validator invariants: fast, fixture-driven, no session setup.
"""

from datetime import date
from typing import Any

from app.models.availability import AvailabilityStatus
from app.models.rule import Rule, RulePhase, RuleScope, RuleSeverity, RuleType
from app.rules.availability_validator import evaluate_availability_rules
from app.rules.types import SlotContext

FRIDAY = date(2026, 10, 2)  # 2026-10-02 is a Friday
SATURDAY = date(2026, 10, 3)
MONDAY = date(2026, 10, 5)


def _rule(
    *,
    type_: RuleType,
    params: dict[str, Any],
    code: str = "r1",
    severity: RuleSeverity = RuleSeverity.HARD,
) -> Rule:
    return Rule(
        code=code,
        name_pl=code,
        name_en=code,
        type=type_,
        scope=RuleScope.GLOBAL,
        params=params,
        severity=severity,
        phase=RulePhase.AVAILABILITY,
        is_active=True,
    )


def _slot(d: date, shift_code: str, status: AvailabilityStatus) -> SlotContext:
    import uuid

    return SlotContext(
        shift_slot_id=uuid.uuid4(), date=d, shift_type_code=shift_code, status=status
    )


def test_min_availability_count_passes_when_enough_declared() -> None:
    rule = _rule(type_=RuleType.MIN_AVAILABILITY_COUNT, params={"n": 2})
    entries = [
        _slot(MONDAY, "MORNING", AvailabilityStatus.AVAILABLE),
        _slot(FRIDAY, "EVENING", AvailabilityStatus.PREFERRED),
    ]

    results = evaluate_availability_rules([rule], entries)

    assert len(results) == 1
    assert results[0].passed is True
    assert results[0].message_params == {"required": 2, "actual": 2}


def test_min_availability_count_ignores_unavailable_rows() -> None:
    rule = _rule(type_=RuleType.MIN_AVAILABILITY_COUNT, params={"n": 2})
    entries = [
        _slot(MONDAY, "MORNING", AvailabilityStatus.AVAILABLE),
        _slot(FRIDAY, "EVENING", AvailabilityStatus.UNAVAILABLE),
    ]

    results = evaluate_availability_rules([rule], entries)

    assert results[0].passed is False
    assert results[0].message_params == {"required": 2, "actual": 1}


def test_min_availability_in_set_matches_weekday_and_shift() -> None:
    rule = _rule(
        type_=RuleType.MIN_AVAILABILITY_IN_SET,
        params={"n": 1, "weekday": "FRI", "shift": "EVENING"},
    )
    entries = [_slot(FRIDAY, "EVENING", AvailabilityStatus.AVAILABLE)]

    results = evaluate_availability_rules([rule], entries)

    assert results[0].passed is True


def test_min_availability_in_set_fails_on_wrong_shift() -> None:
    rule = _rule(
        type_=RuleType.MIN_AVAILABILITY_IN_SET,
        params={"n": 1, "weekday": "FRI", "shift": "EVENING"},
    )
    entries = [_slot(FRIDAY, "MORNING", AvailabilityStatus.AVAILABLE)]

    results = evaluate_availability_rules([rule], entries)

    assert results[0].passed is False
    assert results[0].message_params["actual"] == 0


def test_min_availability_weekend_counts_saturday_and_sunday_only() -> None:
    rule = _rule(type_=RuleType.MIN_AVAILABILITY_WEEKEND, params={"n": 1})
    entries = [_slot(MONDAY, "MORNING", AvailabilityStatus.AVAILABLE)]

    results = evaluate_availability_rules([rule], entries)
    assert results[0].passed is False

    entries.append(_slot(SATURDAY, "MIDDAY", AvailabilityStatus.AVAILABLE))
    results = evaluate_availability_rules([rule], entries)
    assert results[0].passed is True


def test_evaluate_skips_unhandled_rule_types_gracefully() -> None:
    """A schedule-phase rule accidentally passed to the availability
    validator shouldn't crash it - it should just produce no result for
    that rule (the Phase 3 schedule validator is the one that handles it).
    """
    import uuid
    from unittest.mock import MagicMock

    unhandled = MagicMock(spec=Rule)
    unhandled.type = "SOME_FUTURE_TYPE"
    unhandled.code = str(uuid.uuid4())

    results = evaluate_availability_rules([unhandled], [])
    assert results == []
