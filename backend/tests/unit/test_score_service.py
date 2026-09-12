"""Pure tests for the weight-sum invariant and the composite-score formula
(ARCHITECTURE.md ss3.4) - both are plain functions with no DB access, so
they're tested directly rather than through the API (see
tests/unit/test_schedule_validator.py for the same pattern with rules).
"""

import uuid
from decimal import Decimal

import pytest

from app.models.employee_score import EmployeeScore
from app.models.score_criterion import ScoreCriterion
from app.services.score_service import ScoreError, _composite, _validate_active_weights_sum


def _criterion(
    *, weight: str, is_active: bool = True, scale_min: int = 1, scale_max: int = 5
) -> ScoreCriterion:
    return ScoreCriterion(
        id=uuid.uuid4(),
        code=f"c-{uuid.uuid4()}",
        name_pl="x",
        name_en="x",
        weight=Decimal(weight),
        scale_min=scale_min,
        scale_max=scale_max,
        is_active=is_active,
    )


def _score(criterion: ScoreCriterion, value: int) -> EmployeeScore:
    return EmployeeScore(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        criterion_id=criterion.id,
        value=value,
        set_by_user_id=uuid.uuid4(),
    )


def test_active_weights_summing_to_one_is_accepted() -> None:
    criteria = [_criterion(weight="0.4"), _criterion(weight="0.35"), _criterion(weight="0.25")]
    _validate_active_weights_sum(criteria)  # does not raise


def test_active_weights_not_summing_to_one_is_rejected() -> None:
    criteria = [_criterion(weight="0.4"), _criterion(weight="0.35")]
    with pytest.raises(ScoreError) as exc_info:
        _validate_active_weights_sum(criteria)
    assert exc_info.value.message_key == "score_criterion.weights_must_sum_to_one"
    assert exc_info.value.params["total"] == "0.75"


def test_inactive_criteria_are_excluded_from_the_sum() -> None:
    criteria = [_criterion(weight="1.0"), _criterion(weight="0.5", is_active=False)]
    _validate_active_weights_sum(criteria)  # the inactive 0.5 doesn't break the sum


def test_no_active_criteria_is_not_an_error() -> None:
    criteria = [_criterion(weight="0.5", is_active=False)]
    _validate_active_weights_sum(criteria)  # nothing configured yet - not a failure


def test_composite_is_none_when_a_criterion_is_unscored() -> None:
    c1, c2 = _criterion(weight="0.5"), _criterion(weight="0.5")
    entries = {c1.id: _score(c1, 5)}  # c2 never rated

    assert _composite(entries, [c1, c2]) is None


def test_composite_is_none_with_no_active_criteria() -> None:
    assert _composite({}, []) is None


def test_composite_matches_the_architecture_formula() -> None:
    # 100 * sum(weight * (value - scale_min) / (scale_max - scale_min))
    c1, c2 = _criterion(weight="0.5"), _criterion(weight="0.5")
    entries = {c1.id: _score(c1, 5), c2.id: _score(c2, 1)}

    # c1: 0.5 * (5-1)/4 = 0.5 ; c2: 0.5 * (1-1)/4 = 0 -> total 0.5 -> 50.0
    assert _composite(entries, [c1, c2]) == 50.0


def test_composite_is_100_when_everyone_scores_the_maximum() -> None:
    c1, c2 = _criterion(weight="0.6"), _criterion(weight="0.4")
    entries = {c1.id: _score(c1, 5), c2.id: _score(c2, 5)}

    assert _composite(entries, [c1, c2]) == 100.0
