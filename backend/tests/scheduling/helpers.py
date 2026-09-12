"""Shared fixture builders for the solver golden tests
(test_cpsat_golden.py) - the highest-value tests in the repo (CLAUDE.md
"Testing priorities"). Kept out of the test file itself so each test reads
as "given this scenario, these invariants hold" rather than slot/employee
construction boilerplate.
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta

from app.scheduling import (
    AssignmentOutput,
    AvailabilityInput,
    EmployeeInput,
    LockedAssignmentInput,
    SlotInput,
    SolverConfig,
)

DETERMINISTIC_CONFIG = SolverConfig(random_seed=1, num_search_workers=1, time_limit_seconds=10)

MORNING = ("MORNING", time(7, 0), time(15, 0))
MIDDAY = ("MIDDAY", time(11, 0), time(19, 0))
EVENING = ("EVENING", time(15, 0), time(23, 0))

# 2026-03-02 is a Monday.
_DEFAULT_START = date(2026, 3, 2)


def is_weekend(day: date) -> bool:
    return day.weekday() >= 5


def dates_range(count: int, start: date = _DEFAULT_START) -> list[date]:
    return [start + timedelta(days=i) for i in range(count)]


def make_slot(
    day: date,
    shift: tuple[str, time, time] = MORNING,
    *,
    required: int = 2,
    minimum: int = 1,
    maximum: int = 3,
    slot_id: str | None = None,
) -> SlotInput:
    code, start, end = shift
    return SlotInput(
        id=slot_id or f"{day.isoformat()}:{code}",
        date=day,
        shift_type_code=code,
        start_time=start,
        end_time=end,
        required_staff=required,
        min_staff=minimum,
        max_staff=maximum,
        is_weekend=is_weekend(day),
    )


def standard_slots(
    dates: list[date], *, required: int = 2, minimum: int = 1, maximum: int = 3
) -> list[SlotInput]:
    """MORNING + EVENING every day, MIDDAY weekends only - mirrors
    app/seed.py's demo ShiftTypes (ARCHITECTURE.md ss3.2).
    """
    slots: list[SlotInput] = []
    for day in dates:
        slots.append(make_slot(day, MORNING, required=required, minimum=minimum, maximum=maximum))
        slots.append(make_slot(day, EVENING, required=required, minimum=minimum, maximum=maximum))
        if is_weekend(day):
            slots.append(
                make_slot(day, MIDDAY, required=required, minimum=minimum, maximum=maximum)
            )
    return slots


def make_employee(
    employee_id: str,
    *,
    contract_min: int = 5,
    contract_max: int = 18,
    max_consecutive_days: int = 5,
    min_rest_hours: int = 11,
    score: float | None = None,
    preference_debt: int = 0,
    full_name: str | None = None,
) -> EmployeeInput:
    return EmployeeInput(
        id=employee_id,
        full_name=full_name or employee_id,
        contract_min_shifts=contract_min,
        contract_max_shifts=contract_max,
        max_consecutive_days=max_consecutive_days,
        min_rest_hours=min_rest_hours,
        score=score,
        preference_debt=preference_debt,
    )


def available_everywhere(
    employees: list[EmployeeInput], slots: list[SlotInput], level: str = "AVAILABLE"
) -> list[AvailabilityInput]:
    return [
        AvailabilityInput(employee_id=e.id, slot_id=s.id, level=level)  # type: ignore[arg-type]
        for e in employees
        for s in slots
    ]


# --- invariant assertions, shared across every golden test -----------------


def assert_no_double_booking(
    slots_by_id: dict[str, SlotInput], assignments: tuple[AssignmentOutput, ...]
) -> None:
    seen: set[tuple[str, date]] = set()
    for a in assignments:
        key = (a.employee_id, slots_by_id[a.slot_id].date)
        assert key not in seen, f"{a.employee_id} double-booked on {key[1]}"
        seen.add(key)


def assert_no_unavailable_assignment(
    availability: list[AvailabilityInput],
    locked: list[LockedAssignmentInput],
    assignments: tuple[AssignmentOutput, ...],
) -> None:
    declared = {(a.employee_id, a.slot_id) for a in availability}
    locked_pairs = {(entry.employee_id, entry.slot_id) for entry in locked}
    for a in assignments:
        pair = (a.employee_id, a.slot_id)
        assert pair in declared or pair in locked_pairs, f"{pair} assigned without availability"


def assert_max_staff_respected(
    slots_by_id: dict[str, SlotInput], assignments: tuple[AssignmentOutput, ...]
) -> None:
    counts: dict[str, int] = defaultdict(int)
    for a in assignments:
        counts[a.slot_id] += 1
    for slot_id, count in counts.items():
        assert count <= slots_by_id[slot_id].max_staff, f"{slot_id} overstaffed: {count}"


def assert_contract_max_respected(
    employees_by_id: dict[str, EmployeeInput], assignments: tuple[AssignmentOutput, ...]
) -> None:
    counts: dict[str, int] = defaultdict(int)
    for a in assignments:
        counts[a.employee_id] += 1
    for employee_id, count in counts.items():
        assert count <= employees_by_id[employee_id].contract_max_shifts


def assert_min_rest_respected(
    slots_by_id: dict[str, SlotInput],
    employees_by_id: dict[str, EmployeeInput],
    assignments: tuple[AssignmentOutput, ...],
) -> None:
    by_employee: dict[str, list[SlotInput]] = defaultdict(list)
    for a in assignments:
        by_employee[a.employee_id].append(slots_by_id[a.slot_id])
    for employee_id, slots in by_employee.items():
        ordered = sorted(slots, key=lambda s: (s.date, s.start_time))
        for prev, nxt in zip(ordered, ordered[1:], strict=False):
            rest = (
                datetime.combine(nxt.date, nxt.start_time)
                - datetime.combine(prev.date, prev.end_time)
            ).total_seconds() / 3600
            if prev.date == nxt.date:
                continue  # same-day double-booking is a separate invariant
            if (nxt.date - prev.date).days > 1:
                continue  # not adjacent calendar days - rest rule doesn't apply
            assert rest >= employees_by_id[employee_id].min_rest_hours, (
                f"{employee_id} only got {rest}h rest between {prev.id} and {nxt.id}"
            )


def assert_max_consecutive_days_respected(
    slots_by_id: dict[str, SlotInput],
    employees_by_id: dict[str, EmployeeInput],
    assignments: tuple[AssignmentOutput, ...],
) -> None:
    worked_days: dict[str, set[date]] = defaultdict(set)
    for a in assignments:
        worked_days[a.employee_id].add(slots_by_id[a.slot_id].date)
    for employee_id, days in worked_days.items():
        ordered = sorted(days)
        run = 1
        for prev, nxt in zip(ordered, ordered[1:], strict=False):
            run = run + 1 if (nxt - prev).days == 1 else 1
            assert run <= employees_by_id[employee_id].max_consecutive_days, (
                f"{employee_id} worked {run} consecutive days ending {nxt}"
            )


def assert_locked_preserved(
    locked: list[LockedAssignmentInput], assignments: tuple[AssignmentOutput, ...]
) -> None:
    assigned_pairs = {(a.employee_id, a.slot_id) for a in assignments}
    for entry in locked:
        assert (entry.employee_id, entry.slot_id) in assigned_pairs, (
            f"locked assignment {entry} was dropped"
        )
