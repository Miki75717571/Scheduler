from datetime import time

from app.rules.rest_conflicts import ShiftOccurrence, find_impossible_adjacent_pairs
from app.rules.weekdays import Weekday


def _occurrence(code: str, weekday: Weekday, start: time, end: time) -> ShiftOccurrence:
    return ShiftOccurrence(shift_type_code=code, weekday=weekday, start_time=start, end_time=end)


def test_friday_evening_to_saturday_morning_is_flagged_at_11h() -> None:
    occurrences = [
        _occurrence("EVENING", Weekday.FRI, time(15, 0), time(22, 0)),
        _occurrence("MORNING", Weekday.SAT, time(8, 30), time(14, 0)),
    ]

    conflicts = find_impossible_adjacent_pairs(occurrences, min_rest_hours=11)

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.from_shift_type_code == "EVENING"
    assert conflict.from_weekday == Weekday.FRI
    assert conflict.to_shift_type_code == "MORNING"
    assert conflict.to_weekday == Weekday.SAT
    assert conflict.gap_hours == 10.5
    assert conflict.required_hours == 11


def test_same_pair_not_flagged_when_rest_requirement_is_lower() -> None:
    occurrences = [
        _occurrence("EVENING", Weekday.FRI, time(15, 0), time(22, 0)),
        _occurrence("MORNING", Weekday.SAT, time(8, 30), time(14, 0)),
    ]

    assert find_impossible_adjacent_pairs(occurrences, min_rest_hours=10) == []


def test_weekday_pairs_with_enough_rest_are_not_flagged() -> None:
    occurrences = [
        _occurrence("EVENING", Weekday.MON, time(14, 0), time(20, 0)),
        _occurrence("MORNING", Weekday.TUE, time(8, 30), time(14, 0)),
    ]

    # 20:00 -> next day 08:30 is 12.5h, clears an 11h requirement.
    assert find_impossible_adjacent_pairs(occurrences, min_rest_hours=11) == []


def test_sunday_wraps_to_monday() -> None:
    occurrences = [
        _occurrence("EVENING", Weekday.SUN, time(14, 0), time(23, 0)),
        _occurrence("MORNING", Weekday.MON, time(8, 30), time(14, 0)),
    ]

    conflicts = find_impossible_adjacent_pairs(occurrences, min_rest_hours=11)

    assert len(conflicts) == 1
    assert conflicts[0].from_weekday == Weekday.SUN
    assert conflicts[0].to_weekday == Weekday.MON


def test_zero_min_rest_hours_never_conflicts() -> None:
    occurrences = [
        _occurrence("EVENING", Weekday.FRI, time(15, 0), time(23, 59)),
        _occurrence("MORNING", Weekday.SAT, time(0, 0), time(14, 0)),
    ]

    assert find_impossible_adjacent_pairs(occurrences, min_rest_hours=0) == []
