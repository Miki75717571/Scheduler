"""Weekday bitmask shared by ShiftType.active_weekdays and Rule params
(MIN_AVAILABILITY_IN_SET's `weekday` field). Not DB-specific - lives outside
app/scheduling/ (reserved for the solver) and outside app/models/ (it isn't a
table), but is imported by both period generation and the rule handlers.

Bit layout per ARCHITECTURE.md ss3.2: Mon=1 ... Sun=64, i.e. `1 << date.weekday()`
(Python's Monday=0..Sunday=6 lines up exactly with that).
"""

import enum
from datetime import date


class Weekday(enum.StrEnum):
    MON = "MON"
    TUE = "TUE"
    WED = "WED"
    THU = "THU"
    FRI = "FRI"
    SAT = "SAT"
    SUN = "SUN"


_ORDER = [
    Weekday.MON,
    Weekday.TUE,
    Weekday.WED,
    Weekday.THU,
    Weekday.FRI,
    Weekday.SAT,
    Weekday.SUN,
]

ALL_WEEKDAYS_MASK = 127  # 2**7 - 1
WEEKEND_MASK = (1 << 5) | (1 << 6)  # Sat | Sun


def weekday_of(value: date) -> Weekday:
    return _ORDER[value.weekday()]


def weekday_bit(value: date | Weekday) -> int:
    if isinstance(value, Weekday):
        return 1 << _ORDER.index(value)
    return 1 << value.weekday()


def is_weekend(value: date) -> bool:
    return bool(weekday_bit(value) & WEEKEND_MASK)


def active_on(active_weekdays_mask: int, value: date) -> bool:
    return bool(active_weekdays_mask & weekday_bit(value))
