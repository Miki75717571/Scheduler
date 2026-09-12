"""The CP-SAT model (ARCHITECTURE.md ss4.1). Entry point: `solve()`. Pure -
no SQLAlchemy, no session, no I/O (backend/tests/scheduling/test_purity.py
enforces this at import-scan level).

The one modelling decision that matters most: understaffing is a penalised
soft variable, never a hard constraint. Every other "never break this" rule
(unavailability, locks, one-shift-per-day, minimum rest, max consecutive
days, contract ceiling, slot max-staff) is hard, but each is encoded through
`_bounded_sum_hard`, which silently stops enforcing a group the moment
manager locks alone already exceed its limit - a pre-existing manual
violation must never make the whole model INFEASIBLE. See that helper's
docstring for why.
"""

import time as _time
from collections import defaultdict
from datetime import date as date_
from datetime import datetime, timedelta
from datetime import time as time_

from ortools.sat.python import cp_model

from app.scheduling.domain import (
    AssignmentOutput,
    AvailabilityLevel,
    Diagnostics,
    SolverInput,
    SolverOutput,
    SolverStats,
)
from app.scheduling.explain import build_diagnostics, build_stats

_PREFERRED_DESIRABILITY = 10
_AVAILABLE_DESIRABILITY = 3


def _score_int(score: float | None) -> int:
    if score is None:
        return 0
    return max(0, min(100, round(score)))


def _rest_hours(day_a: date_, end_a: time_, day_b: date_, start_b: time_) -> float:
    delta = datetime.combine(day_b, start_b) - datetime.combine(day_a, end_a)
    return delta.total_seconds() / 3600


def _bounded_sum_hard(
    model: cp_model.CpModel,
    free_vars: list[cp_model.IntVar],
    locked_count: int,
    limit: int,
) -> None:
    """A hard "sum of this group <= limit" constraint, tolerant of manager
    locks that already occupy part (or all, or more than all) of the
    capacity. If locks alone already exceed `limit`, no constraint is added
    for this group at all - the pre-existing violation is left exactly as
    the manager made it, and the model stays feasible. Otherwise the free
    variables are capped at whatever capacity the locks haven't already used
    (which may be zero, correctly forcing them all to 0).
    """
    if locked_count > limit:
        return
    if free_vars:
        model.add(cp_model.LinearExpr.sum(free_vars) <= limit - locked_count)


def _empty_diagnostics_and_stats(
    input: SolverInput, assignments: tuple[AssignmentOutput, ...]
) -> tuple[Diagnostics, SolverStats]:
    diagnostics = build_diagnostics(input, assignments)
    stats = build_stats(input, assignments, diagnostics)
    return diagnostics, stats


def _degenerate_result(input: SolverInput, *, status: str, start: float) -> SolverOutput:
    """No employees or no slots: nothing for CP-SAT to do. Still returns a
    coherent, explainable output rather than raising - ARCHITECTURE.md ss1's
    "everything comes out as plain data structures" applies to the empty
    case too (CLAUDE.md "Handle the degenerate cases").
    """
    diagnostics, stats = _empty_diagnostics_and_stats(input, ())
    return SolverOutput(
        status=status,
        objective_value=None,
        assignments=(),
        diagnostics=diagnostics,
        stats=stats,
        solve_time_ms=round((_time.perf_counter() - start) * 1000),
    )


def solve(input: SolverInput) -> SolverOutput:
    start = _time.perf_counter()

    if not input.employees:
        return _degenerate_result(input, status="NO_EMPLOYEES", start=start)
    if not input.slots:
        return _degenerate_result(input, status="NO_SLOTS", start=start)

    weights = input.weights
    employees_by_id = {e.id: e for e in input.employees}
    slots_by_id = {s.id: s for s in input.slots}

    locked_pairs = {
        (locked.employee_id, locked.slot_id)
        for locked in input.locked_assignments
        if locked.employee_id in employees_by_id and locked.slot_id in slots_by_id
    }
    availability_level: dict[tuple[str, str], AvailabilityLevel] = {
        (a.employee_id, a.slot_id): a.level
        for a in input.availability
        if a.employee_id in employees_by_id and a.slot_id in slots_by_id
    }

    # A variable exists only where it could ever be 1: declared
    # AVAILABLE/PREFERRED, or a manager lock (which may pin someone who never
    # declared availability at all).
    pair_keys = set(availability_level) | locked_pairs
    model = cp_model.CpModel()
    x: dict[tuple[str, str], cp_model.IntVar] = {
        pair: model.new_bool_var(f"x_{pair[0]}_{pair[1]}") for pair in pair_keys
    }
    for pair in locked_pairs:
        model.add(x[pair] == 1)

    pairs_by_employee: dict[str, list[tuple[str, str]]] = defaultdict(list)
    pairs_by_slot: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for pair in pair_keys:
        pairs_by_employee[pair[0]].append(pair)
        pairs_by_slot[pair[1]].append(pair)

    def free_and_locked(pairs: list[tuple[str, str]]) -> tuple[list[cp_model.IntVar], int]:
        free = [x[p] for p in pairs if p not in locked_pairs]
        locked_count = len(pairs) - len(free)
        return free, locked_count

    # --- hard: never exceed a slot's max_staff -----------------------------
    for slot in input.slots:
        free, locked_count = free_and_locked(pairs_by_slot.get(slot.id, []))
        _bounded_sum_hard(model, free, locked_count, limit=slot.max_staff)

    # --- hard: one shift per person per day, and a "worked that day"
    # indicator (used by max-consecutive-days below) that stays a true 0/1
    # even in the pathological case where locks alone already broke the
    # one-shift-per-day rule for that employee/day. ------------------------
    work_day: dict[tuple[str, date_], cp_model.IntVar] = {}
    pairs_by_employee_day: dict[tuple[str, date_], list[tuple[str, str]]] = defaultdict(list)
    for pair in pair_keys:
        pairs_by_employee_day[(pair[0], slots_by_id[pair[1]].date)].append(pair)

    for (employee_id, day), pairs in pairs_by_employee_day.items():
        free, locked_count = free_and_locked(pairs)
        _bounded_sum_hard(model, free, locked_count, limit=1)

        day_var = model.new_bool_var(f"worked_{employee_id}_{day.isoformat()}")
        model.add_max_equality(day_var, [x[p] for p in pairs])
        work_day[(employee_id, day)] = day_var

    # --- hard: minimum rest between shifts on consecutive calendar days ---
    for employee in input.employees:
        employee_days = {d for (eid, d) in pairs_by_employee_day if eid == employee.id}
        for day in sorted(employee_days):
            next_day = day + timedelta(days=1)
            if next_day not in employee_days:
                continue
            for pair_a in pairs_by_employee_day[(employee.id, day)]:
                slot_a = slots_by_id[pair_a[1]]
                for pair_b in pairs_by_employee_day[(employee.id, next_day)]:
                    slot_b = slots_by_id[pair_b[1]]
                    rest = _rest_hours(day, slot_a.end_time, next_day, slot_b.start_time)
                    if rest >= employee.min_rest_hours:
                        continue
                    free, locked_count = free_and_locked([pair_a, pair_b])
                    _bounded_sum_hard(model, free, locked_count, limit=1)

    # --- hard: max consecutive working days (sliding window) --------------
    all_dates = sorted({s.date for s in input.slots})
    if all_dates:
        span_days = (all_dates[-1] - all_dates[0]).days + 1
        full_span = [all_dates[0] + timedelta(days=i) for i in range(span_days)]
        for employee in input.employees:
            window = employee.max_consecutive_days + 1
            if window > len(full_span):
                continue
            for start_idx in range(len(full_span) - window + 1):
                window_days = full_span[start_idx : start_idx + window]
                window_vars = [
                    work_day[(employee.id, d)] for d in window_days if (employee.id, d) in work_day
                ]
                if not window_vars:
                    continue
                locked_days_in_window = sum(
                    1
                    for d in window_days
                    if any(
                        p in locked_pairs for p in pairs_by_employee_day.get((employee.id, d), [])
                    )
                )
                if locked_days_in_window > employee.max_consecutive_days:
                    continue
                model.add(cp_model.LinearExpr.sum(window_vars) <= employee.max_consecutive_days)

    # --- hard: contract ceiling ---------------------------------------------
    for employee in input.employees:
        free, locked_count = free_and_locked(pairs_by_employee.get(employee.id, []))
        _bounded_sum_hard(model, free, locked_count, limit=employee.contract_max_shifts)

    # --- objective -----------------------------------------------------------
    objective_terms: list[cp_model.LinearExprT] = []

    for slot in input.slots:
        assigned_expr = cp_model.LinearExpr.sum([x[p] for p in pairs_by_slot.get(slot.id, [])])
        under = model.new_int_var(0, slot.required_staff, f"under_{slot.id}")
        model.add(under >= slot.required_staff - assigned_expr)
        objective_terms.append(weights.understaffing * under)

    for employee in input.employees:
        workload = cp_model.LinearExpr.sum([x[p] for p in pairs_by_employee.get(employee.id, [])])
        shortfall = model.new_int_var(0, employee.contract_min_shifts, f"shortfall_{employee.id}")
        model.add(shortfall >= employee.contract_min_shifts - workload)
        objective_terms.append(weights.contract_min_shortfall * shortfall)

    for pair, pair_level in availability_level.items():
        if pair_level != "PREFERRED":
            continue
        objective_terms.append(weights.denied_preference * (1 - x[pair]))
        employee = employees_by_id[pair[0]]
        objective_terms.append(-weights.preference_debt * employee.preference_debt * x[pair])

    for pair in pair_keys:
        employee = employees_by_id[pair[0]]
        pair_level = availability_level.get(pair, "AVAILABLE")
        desirability = (
            _PREFERRED_DESIRABILITY if pair_level == "PREFERRED" else _AVAILABLE_DESIRABILITY
        )
        coefficient = weights.score_weight * _score_int(employee.score) * desirability
        if coefficient:
            objective_terms.append(-coefficient * x[pair])

    total_slots = len(input.slots)
    workloads = {
        e.id: cp_model.LinearExpr.sum([x[p] for p in pairs_by_employee.get(e.id, [])])
        for e in input.employees
    }
    max_workload = model.new_int_var(0, total_slots, "max_workload")
    min_workload = model.new_int_var(0, total_slots, "min_workload")
    for workload in workloads.values():
        model.add(max_workload >= workload)
        model.add(min_workload <= workload)
    objective_terms.append(weights.fairness_spread * (max_workload - min_workload))

    unpopular_counts = {
        e.id: cp_model.LinearExpr.sum(
            [x[p] for p in pairs_by_employee.get(e.id, []) if slots_by_id[p[1]].is_weekend]
        )
        for e in input.employees
    }
    max_unpopular = model.new_int_var(0, total_slots, "max_unpopular")
    min_unpopular = model.new_int_var(0, total_slots, "min_unpopular")
    for count in unpopular_counts.values():
        model.add(max_unpopular >= count)
        model.add(min_unpopular <= count)
    objective_terms.append(weights.unpopular_shift_spread * (max_unpopular - min_unpopular))

    model.minimize(cp_model.LinearExpr.sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = input.config.time_limit_seconds
    solver.parameters.random_seed = input.config.random_seed
    solver.parameters.num_search_workers = input.config.num_search_workers
    cp_status = solver.solve(model)

    solve_time_ms = round((_time.perf_counter() - start) * 1000)

    if cp_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        assignments = tuple(
            AssignmentOutput(employee_id=p[0], slot_id=p[1], is_locked=p in locked_pairs)
            for p in pair_keys
            if solver.value(x[p]) == 1
        )
        status = "OPTIMAL" if cp_status == cp_model.OPTIMAL else "FEASIBLE"
        objective_value: float | None = solver.objective_value
    else:
        # Should not be reachable given the modelling above (every hard group
        # degrades gracefully around pre-existing lock conflicts instead of
        # tightening past feasibility) - kept as a last-resort guarantee that
        # "solve" never raises and never returns nothing at all, per
        # CLAUDE.md's "must NEVER return INFEASIBLE".
        assignments = tuple(
            AssignmentOutput(employee_id=p[0], slot_id=p[1], is_locked=True) for p in locked_pairs
        )
        status = "INFEASIBLE_FALLBACK"
        objective_value = None

    diagnostics, stats = _empty_diagnostics_and_stats(input, assignments)
    return SolverOutput(
        status=status,
        objective_value=objective_value,
        assignments=assignments,
        diagnostics=diagnostics,
        stats=stats,
        solve_time_ms=solve_time_ms,
    )
