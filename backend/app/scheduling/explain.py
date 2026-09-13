"""Human-readable diagnostics and summary stats, built purely from
SolverInput + the final assignments - no solver internals leak in here, so
the same functions can (and do, in tests) explain a hand-written assignment
set with no CP-SAT involved at all.

Every diagnostic carries a message_key + message_params, never an English
sentence (CLAUDE.md "i18n") - translation happens in the frontend once the
generate screen exists.
"""

from collections import defaultdict
from datetime import date as date_
from datetime import datetime, timedelta
from datetime import time as time_

from app.scheduling.domain import (
    AssignmentOutput,
    Diagnostics,
    EmployeeDiagnostic,
    SlotDiagnostic,
    SlotInput,
    SolverInput,
    SolverStats,
    UnusedAvailableEmployee,
)


def _assigned_by_slot(assignments: tuple[AssignmentOutput, ...]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for a in assignments:
        counts[a.slot_id] += 1
    return counts


def _assigned_by_employee(assignments: tuple[AssignmentOutput, ...]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for a in assignments:
        counts[a.employee_id] += 1
    return counts


def _rest_hours(day_a: date_, end_a: time_, day_b: date_, start_b: time_) -> float:
    """Duplicated from app/scheduling/cpsat.py deliberately - see this
    module's docstring: explain.py must stand alone from the solver's own
    internals so it can explain a hand-written assignment set too.
    """
    delta = datetime.combine(day_b, start_b) - datetime.combine(day_a, end_a)
    return delta.total_seconds() / 3600


def _longest_run(days: set[date_]) -> int:
    if not days:
        return 0
    ordered = sorted(days)
    longest = 1
    current = 1
    for previous, current_day in zip(ordered, ordered[1:], strict=False):
        current = current + 1 if (current_day - previous).days == 1 else 1
        longest = max(longest, current)
    return longest


def _unused_reason(
    employee_id: str,
    full_name: str,
    slot: SlotInput,
    *,
    assigned_slots_by_employee_day: dict[tuple[str, date_], list[SlotInput]],
    assigned_count_by_employee: dict[str, int],
    assigned_dates_by_employee: dict[str, set[date_]],
    contract_max_shifts: int,
    min_rest_hours: int,
    max_consecutive_days: int,
) -> tuple[str, dict[str, object]]:
    same_day = assigned_slots_by_employee_day.get((employee_id, slot.date), [])
    if same_day:
        return "solver.unused_already_assigned_same_day", {
            "shift_type_code": same_day[0].shift_type_code
        }

    if assigned_count_by_employee.get(employee_id, 0) >= contract_max_shifts:
        return "solver.unused_contract_max_reached", {"contract_max_shifts": contract_max_shifts}

    for offset in (-1, 1):
        neighbor_day = slot.date + timedelta(days=offset)
        for neighbor in assigned_slots_by_employee_day.get((employee_id, neighbor_day), []):
            rest = (
                _rest_hours(neighbor_day, neighbor.end_time, slot.date, slot.start_time)
                if offset == -1
                else _rest_hours(slot.date, slot.end_time, neighbor_day, neighbor.start_time)
            )
            if rest < min_rest_hours:
                return "solver.unused_rest_rule", {
                    "required": min_rest_hours,
                    "actual": round(rest, 1),
                }

    hypothetical_days = assigned_dates_by_employee.get(employee_id, set()) | {slot.date}
    if _longest_run(hypothetical_days) > max_consecutive_days:
        return "solver.unused_max_consecutive_days", {"allowed": max_consecutive_days}

    return "solver.unused_not_prioritized", {}


def _unused_available_for_slot(
    input: SolverInput,
    slot: SlotInput,
    assigned_pairs: set[tuple[str, str]],
) -> tuple[UnusedAvailableEmployee, ...]:
    employees_by_id = {e.id: e for e in input.employees}
    slots_by_id = {s.id: s for s in input.slots}

    assigned_slots_by_employee_day: dict[tuple[str, date_], list[SlotInput]] = defaultdict(list)
    assigned_count_by_employee: dict[str, int] = defaultdict(int)
    assigned_dates_by_employee: dict[str, set[date_]] = defaultdict(set)
    for employee_id, assigned_slot_id in assigned_pairs:
        assigned_slot = slots_by_id.get(assigned_slot_id)
        if assigned_slot is None:
            continue
        assigned_slots_by_employee_day[(employee_id, assigned_slot.date)].append(assigned_slot)
        assigned_count_by_employee[employee_id] += 1
        assigned_dates_by_employee[employee_id].add(assigned_slot.date)

    unused: list[UnusedAvailableEmployee] = []
    for a in input.availability:
        if a.slot_id != slot.id or (a.employee_id, slot.id) in assigned_pairs:
            continue
        employee = employees_by_id.get(a.employee_id)
        if employee is None:
            continue
        message_key, params = _unused_reason(
            employee.id,
            employee.full_name,
            slot,
            assigned_slots_by_employee_day=assigned_slots_by_employee_day,
            assigned_count_by_employee=assigned_count_by_employee,
            assigned_dates_by_employee=assigned_dates_by_employee,
            contract_max_shifts=employee.contract_max_shifts,
            min_rest_hours=employee.min_rest_hours,
            max_consecutive_days=employee.max_consecutive_days,
        )
        unused.append(
            UnusedAvailableEmployee(
                employee_id=employee.id,
                full_name=employee.full_name,
                level=a.level,
                message_key=message_key,
                message_params=params,
            )
        )
    return tuple(unused)


def build_diagnostics(input: SolverInput, assignments: tuple[AssignmentOutput, ...]) -> Diagnostics:
    assigned_by_slot = _assigned_by_slot(assignments)
    assigned_by_employee = _assigned_by_employee(assignments)
    assigned_pairs = {(a.employee_id, a.slot_id) for a in assignments}

    available_by_slot: dict[str, int] = defaultdict(int)
    declared_by_employee: dict[str, int] = defaultdict(int)
    for a in input.availability:
        available_by_slot[a.slot_id] += 1
        declared_by_employee[a.employee_id] += 1

    slot_diagnostics: list[SlotDiagnostic] = []
    for slot in input.slots:
        assigned = assigned_by_slot.get(slot.id, 0)
        if assigned >= slot.required_staff:
            continue
        slot_diagnostics.append(
            SlotDiagnostic(
                slot_id=slot.id,
                date=slot.date,
                shift_type_code=slot.shift_type_code,
                required_staff=slot.required_staff,
                min_staff=slot.min_staff,
                assigned_staff=assigned,
                available_staff=available_by_slot.get(slot.id, 0),
                message_key="solver.slot_understaffed",
                message_params={
                    "date": slot.date.isoformat(),
                    "shift_type_code": slot.shift_type_code,
                    "required_staff": slot.required_staff,
                    "assigned_staff": assigned,
                    "available_staff": available_by_slot.get(slot.id, 0),
                },
                unused_available=_unused_available_for_slot(input, slot, assigned_pairs),
            )
        )

    employee_diagnostics: list[EmployeeDiagnostic] = []
    for employee in input.employees:
        assigned = assigned_by_employee.get(employee.id, 0)
        if assigned >= employee.contract_min_shifts:
            continue
        employee_diagnostics.append(
            EmployeeDiagnostic(
                employee_id=employee.id,
                assigned_count=assigned,
                contract_min_shifts=employee.contract_min_shifts,
                shortfall=employee.contract_min_shifts - assigned,
                declared_count=declared_by_employee.get(employee.id, 0),
                message_key="solver.employee_below_contract_min",
                message_params={
                    "employee_id": employee.id,
                    "full_name": employee.full_name,
                    "assigned_count": assigned,
                    "contract_min_shifts": employee.contract_min_shifts,
                    "shortfall": employee.contract_min_shifts - assigned,
                    "declared_count": declared_by_employee.get(employee.id, 0),
                },
            )
        )

    return Diagnostics(
        slot_diagnostics=tuple(slot_diagnostics), employee_diagnostics=tuple(employee_diagnostics)
    )


def build_stats(
    input: SolverInput, assignments: tuple[AssignmentOutput, ...], diagnostics: Diagnostics
) -> SolverStats:
    assigned_by_slot = _assigned_by_slot(assignments)
    assigned_by_employee = _assigned_by_employee(assignments)

    total_required_staff = sum(s.required_staff for s in input.slots)
    # Capped per-slot so one overstaffed slot can't mask a genuinely
    # understaffed one when averaged into a single headline percentage.
    covered = sum(min(assigned_by_slot.get(s.id, 0), s.required_staff) for s in input.slots)
    coverage_rate = (covered / total_required_staff) if total_required_staff > 0 else 1.0

    assigned_pairs = {(a.employee_id, a.slot_id) for a in assignments}
    preferred_pairs = [
        (a.employee_id, a.slot_id) for a in input.availability if a.level == "PREFERRED"
    ]
    preference_satisfaction_rate = (
        sum(1 for p in preferred_pairs if p in assigned_pairs) / len(preferred_pairs)
        if preferred_pairs
        else None
    )

    shifts_per_employee = {e.id: assigned_by_employee.get(e.id, 0) for e in input.employees}
    fairness_spread = (
        max(shifts_per_employee.values()) - min(shifts_per_employee.values())
        if shifts_per_employee
        else 0
    )

    return SolverStats(
        total_slots=len(input.slots),
        total_required_staff=total_required_staff,
        total_assigned=len(assignments),
        understaffed_slot_count=len(diagnostics.slot_diagnostics),
        coverage_rate=coverage_rate,
        preference_satisfaction_rate=preference_satisfaction_rate,
        fairness_spread=fairness_spread,
        shifts_per_employee=shifts_per_employee,
    )
