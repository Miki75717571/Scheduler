"""Resolves the EFFECTIVE start_time/end_time/staffing for a ShiftType on a
specific date, per CLAUDE.md's per-weekday override design: a ShiftType keeps
its own values as the fallback, and a ShiftTypeWeekdayOverride row (if one
exists for that weekday) supplies the real values instead. Every consumer
that used to read ShiftType.start_time/end_time or default_*_staff directly
(slot generation, the solver, the schedule validator, the API's slot
serialization) must go through `resolve_effective_config` instead so they all
agree on what a given (shift_type, date) pair actually means.
"""

from dataclasses import dataclass
from datetime import date as date_
from datetime import time as time_

from app.models.shift_type import ShiftType
from app.models.shift_type_weekday_override import ShiftTypeWeekdayOverride
from app.rules.weekdays import Weekday, weekday_of


@dataclass(frozen=True)
class EffectiveShiftConfig:
    start_time: time_
    end_time: time_
    min_staff: int
    required_staff: int
    max_staff: int


def resolve_effective_config(
    shift_type: ShiftType,
    overrides_by_weekday: dict[Weekday, ShiftTypeWeekdayOverride],
    target_date: date_,
) -> EffectiveShiftConfig:
    override = overrides_by_weekday.get(weekday_of(target_date))
    if override is not None:
        return EffectiveShiftConfig(
            start_time=override.start_time,
            end_time=override.end_time,
            min_staff=override.min_staff,
            required_staff=override.required_staff,
            max_staff=override.max_staff,
        )
    return EffectiveShiftConfig(
        start_time=shift_type.start_time,
        end_time=shift_type.end_time,
        min_staff=shift_type.default_min_staff,
        required_staff=shift_type.default_required_staff,
        max_staff=shift_type.default_max_staff,
    )


def overrides_by_weekday_for(
    overrides: list[ShiftTypeWeekdayOverride],
) -> dict[Weekday, ShiftTypeWeekdayOverride]:
    return {o.weekday: o for o in overrides}
