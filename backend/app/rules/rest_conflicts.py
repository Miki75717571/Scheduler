"""Detects when a configured MIN_REST_HOURS value makes a specific
(shift_type, weekday) -> (shift_type, next weekday) pair structurally
impossible for the same person to work - e.g. Friday EVENING ending 22:00
followed by Saturday MORNING starting 08:30 is a 10.5h gap, under an 11h
minimum. CLAUDE.md JOB 4 is explicit this must be *surfaced*, never silently
resolved by quietly loosening the rule - see the two call sites: the admin
rules screen (app/api/v1/rules.py) and solver diagnostics
(app/scheduling/explain.py).

Pure - plain values in, plain dataclasses out - so it can run identically
against live shift config (impure caller) or a test fixture.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from app.rules.weekdays import Weekday

_WEEKDAY_ORDER = [
    Weekday.MON,
    Weekday.TUE,
    Weekday.WED,
    Weekday.THU,
    Weekday.FRI,
    Weekday.SAT,
    Weekday.SUN,
]


def _next_weekday(weekday: Weekday) -> Weekday:
    return _WEEKDAY_ORDER[(_WEEKDAY_ORDER.index(weekday) + 1) % 7]


@dataclass(frozen=True)
class ShiftOccurrence:
    """One (shift_type, weekday) that actually generates a slot, with just
    its effective start/end time - callers resolve that via
    app/services/shift_effective.py before building this (kept as plain
    values here, not an EffectiveShiftConfig, so this module has no
    service-layer dependency)."""

    shift_type_code: str
    weekday: Weekday
    start_time: time
    end_time: time


@dataclass(frozen=True)
class RestConflict:
    from_shift_type_code: str
    from_weekday: Weekday
    to_shift_type_code: str
    to_weekday: Weekday
    gap_hours: float
    required_hours: int


def find_impossible_adjacent_pairs(
    occurrences: list[ShiftOccurrence], min_rest_hours: int
) -> list[RestConflict]:
    """Checks every occurrence ending on weekday `d` against every occurrence
    starting on weekday `d+1` (Sunday wraps to Monday - the check is about a
    recurring weekly pattern, not a specific date) and flags gaps below
    `min_rest_hours`. A world with no shift types configured, or a
    min_rest_hours of 0, naturally returns no conflicts.
    """
    if min_rest_hours <= 0:
        return []

    by_weekday: dict[Weekday, list[ShiftOccurrence]] = {w: [] for w in _WEEKDAY_ORDER}
    for occurrence in occurrences:
        by_weekday[occurrence.weekday].append(occurrence)

    conflicts: list[RestConflict] = []
    base_day = datetime(2024, 1, 1)  # arbitrary Monday; only weekday deltas matter
    for weekday in _WEEKDAY_ORDER:
        next_weekday = _next_weekday(weekday)
        day_a = base_day + timedelta(days=_WEEKDAY_ORDER.index(weekday))
        day_b = base_day + timedelta(days=_WEEKDAY_ORDER.index(weekday) + 1)
        for occurrence_a in by_weekday[weekday]:
            for occurrence_b in by_weekday[next_weekday]:
                gap = (
                    datetime.combine(day_b.date(), occurrence_b.start_time)
                    - datetime.combine(day_a.date(), occurrence_a.end_time)
                ).total_seconds() / 3600
                if gap < min_rest_hours:
                    conflicts.append(
                        RestConflict(
                            from_shift_type_code=occurrence_a.shift_type_code,
                            from_weekday=weekday,
                            to_shift_type_code=occurrence_b.shift_type_code,
                            to_weekday=next_weekday,
                            gap_hours=round(gap, 1),
                            required_hours=min_rest_hours,
                        )
                    )
    return conflicts
