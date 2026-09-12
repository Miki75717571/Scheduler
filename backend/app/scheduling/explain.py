"""Human-readable diagnostics and summary stats, built purely from
SolverInput + the final assignments - no solver internals leak in here, so
the same functions can (and do, in tests) explain a hand-written assignment
set with no CP-SAT involved at all.

Every diagnostic carries a message_key + message_params, never an English
sentence (CLAUDE.md "i18n") - translation happens in the frontend once the
generate screen exists.
"""

from collections import defaultdict

from app.scheduling.domain import (
    AssignmentOutput,
    Diagnostics,
    EmployeeDiagnostic,
    SlotDiagnostic,
    SolverInput,
    SolverStats,
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


def build_diagnostics(input: SolverInput, assignments: tuple[AssignmentOutput, ...]) -> Diagnostics:
    assigned_by_slot = _assigned_by_slot(assignments)
    assigned_by_employee = _assigned_by_employee(assignments)

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
