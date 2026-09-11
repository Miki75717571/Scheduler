"""Shape validation for Rule.params, per RuleType. Called from
app/services/rule_service.py at create/update time so a malformed rule is
rejected with a message key at the API boundary rather than blowing up the
first time a handler in availability_validator.py tries to read it.
"""

from typing import Any

from app.models.rule import RuleType
from app.rules.weekdays import Weekday


class RuleParamsError(Exception):
    def __init__(self, message_key: str, params: dict[str, Any] | None = None) -> None:
        self.message_key = message_key
        self.params = params or {}
        super().__init__(message_key)


def _require_non_negative_int(params: dict[str, Any], key: str) -> None:
    value = params.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RuleParamsError("rule.invalid_params", {"field": key})


def _reject_unknown_fields(params: dict[str, Any], allowed: set[str]) -> None:
    extra = set(params) - allowed
    if extra:
        raise RuleParamsError("rule.invalid_params", {"field": sorted(extra)[0]})


def validate_rule_params(rule_type: RuleType, params: dict[str, Any]) -> None:
    if (
        rule_type == RuleType.MIN_AVAILABILITY_COUNT
        or rule_type == RuleType.MIN_AVAILABILITY_WEEKEND
    ):
        _require_non_negative_int(params, "n")
        _reject_unknown_fields(params, {"n"})

    elif rule_type == RuleType.MIN_AVAILABILITY_IN_SET:
        _require_non_negative_int(params, "n")
        if params.get("weekday") not in {w.value for w in Weekday}:
            raise RuleParamsError("rule.invalid_params", {"field": "weekday"})
        shift = params.get("shift")
        if not isinstance(shift, str) or not shift:
            raise RuleParamsError("rule.invalid_params", {"field": "shift"})
        _reject_unknown_fields(params, {"n", "weekday", "shift"})

    else:
        raise RuleParamsError("rule.unsupported_type")
