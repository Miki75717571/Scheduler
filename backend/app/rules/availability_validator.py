"""The availability-phase rule engine: given a Rule row (data, from the DB)
and the slots an employee has marked, decide pass/fail. Deliberately mirrors
app/scheduling/'s purity - no DB session, no ORM - so `evaluate_availability_rules`
is a plain function you can unit test with fixture lists (see
tests/unit/test_availability_validator.py) instead of spinning up a database.

New rule types get a handler registered here via @rule_handler, never an
`if rule.type == ...` scattered through a service (CLAUDE.md "Rules as data").
"""

from collections.abc import Callable
from typing import Any

from app.models.availability import AvailabilityStatus
from app.models.rule import Rule, RuleType
from app.rules.types import RuleCheckResult, SlotContext
from app.rules.weekdays import Weekday, is_weekend, weekday_of

Handler = Callable[[Rule, list[SlotContext]], RuleCheckResult]

_REGISTRY: dict[RuleType, Handler] = {}


def rule_handler(rule_type: RuleType) -> Callable[[Handler], Handler]:
    def _register(fn: Handler) -> Handler:
        _REGISTRY[rule_type] = fn
        return fn

    return _register


def _declared(entries: list[SlotContext]) -> list[SlotContext]:
    return [e for e in entries if e.status != AvailabilityStatus.UNAVAILABLE]


def _result(
    rule: Rule, message_key: str, passed: bool, message_params: dict[str, Any]
) -> RuleCheckResult:
    return RuleCheckResult(
        rule_code=rule.code,
        rule_type=rule.type.value,
        severity=rule.severity.value,
        passed=passed,
        message_key=message_key,
        message_params=message_params,
    )


@rule_handler(RuleType.MIN_AVAILABILITY_COUNT)
def _check_min_availability_count(rule: Rule, entries: list[SlotContext]) -> RuleCheckResult:
    required = int(rule.params["n"])
    actual = len(_declared(entries))
    return _result(
        rule,
        "rules.MIN_AVAILABILITY_COUNT",
        actual >= required,
        {"required": required, "actual": actual},
    )


@rule_handler(RuleType.MIN_AVAILABILITY_WEEKEND)
def _check_min_availability_weekend(rule: Rule, entries: list[SlotContext]) -> RuleCheckResult:
    required = int(rule.params["n"])
    actual = sum(1 for e in _declared(entries) if is_weekend(e.date))
    return _result(
        rule,
        "rules.MIN_AVAILABILITY_WEEKEND",
        actual >= required,
        {"required": required, "actual": actual},
    )


@rule_handler(RuleType.MIN_AVAILABILITY_IN_SET)
def _check_min_availability_in_set(rule: Rule, entries: list[SlotContext]) -> RuleCheckResult:
    required = int(rule.params["n"])
    weekday = Weekday(rule.params["weekday"])
    shift_code = str(rule.params["shift"])
    actual = sum(
        1
        for e in _declared(entries)
        if e.shift_type_code == shift_code and weekday_of(e.date) == weekday
    )
    return _result(
        rule,
        "rules.MIN_AVAILABILITY_IN_SET",
        actual >= required,
        {"required": required, "actual": actual, "weekday": weekday.value, "shift": shift_code},
    )


def evaluate_availability_rules(
    rules: list[Rule], entries: list[SlotContext]
) -> list[RuleCheckResult]:
    results: list[RuleCheckResult] = []
    for rule in rules:
        handler = _REGISTRY.get(rule.type)
        if handler is None:
            continue
        results.append(handler(rule, entries))
    return results
