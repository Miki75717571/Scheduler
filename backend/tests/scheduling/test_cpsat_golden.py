"""Golden fixture tests for the CP-SAT solver (ARCHITECTURE.md ss4.4).
These are, per CLAUDE.md, the most important tests in the codebase: they
assert INVARIANTS (nobody double-booked, no assignment against declared
unavailability, every hard rule holds, locks survive, coverage is sane) - not
exact rosters, since CP-SAT can return different equally-optimal solutions
between runs. `random_seed` is pinned and `num_search_workers=1` throughout
for determinism.
"""

from app.scheduling import (
    AvailabilityInput,
    LockedAssignmentInput,
    SolverInput,
    SolverOutput,
    SolverWeights,
    solve,
)
from tests.scheduling.helpers import (
    DETERMINISTIC_CONFIG,
    EVENING,
    MORNING,
    assert_contract_max_respected,
    assert_locked_preserved,
    assert_max_consecutive_days_respected,
    assert_max_staff_respected,
    assert_min_rest_respected,
    assert_no_double_booking,
    assert_no_unavailable_assignment,
    available_everywhere,
    dates_range,
    make_employee,
    make_slot,
    standard_slots,
)


def _assert_all_hard_rules(inp: SolverInput, output: SolverOutput) -> None:
    slots_by_id = {s.id: s for s in inp.slots}
    employees_by_id = {e.id: e for e in inp.employees}
    assert_no_double_booking(slots_by_id, output.assignments)
    assert_no_unavailable_assignment(
        list(inp.availability), list(inp.locked_assignments), output.assignments
    )
    assert_max_staff_respected(slots_by_id, output.assignments)
    assert_contract_max_respected(employees_by_id, output.assignments)
    assert_min_rest_respected(slots_by_id, employees_by_id, output.assignments)
    assert_max_consecutive_days_respected(slots_by_id, employees_by_id, output.assignments)


def test_normal_month_gets_near_full_coverage() -> None:
    dates = dates_range(14)
    slots = standard_slots(dates, required=2, minimum=1, maximum=3)
    employees = [make_employee(f"e{i}", contract_min=4, contract_max=18) for i in range(8)]
    availability = available_everywhere(employees, slots)

    inp = SolverInput(
        period_id="p",
        slots=tuple(slots),
        employees=tuple(employees),
        availability=tuple(availability),
        config=DETERMINISTIC_CONFIG,
    )
    output = solve(inp)

    assert output.status in ("OPTIMAL", "FEASIBLE")
    _assert_all_hard_rules(inp, output)
    assert output.stats.coverage_rate >= 0.95


def test_everyone_wants_mornings_leaves_other_shifts_understaffed_not_broken() -> None:
    dates = dates_range(7)
    slots = standard_slots(dates, required=2, minimum=1, maximum=3)
    employees = [make_employee(f"e{i}", contract_min=3, contract_max=18) for i in range(4)]

    availability = [
        AvailabilityInput(employee_id=e.id, slot_id=s.id, level="PREFERRED")
        for e in employees
        for s in slots
        if s.shift_type_code == "MORNING"
    ]

    inp = SolverInput(
        period_id="p",
        slots=tuple(slots),
        employees=tuple(employees),
        availability=tuple(availability),
        config=DETERMINISTIC_CONFIG,
    )
    output = solve(inp)

    assert output.status in ("OPTIMAL", "FEASIBLE")
    _assert_all_hard_rules(inp, output)
    # Nobody ever declared availability for EVENING/MIDDAY, so every such slot
    # is understaffed - the solver's failure output becoming the feature
    # (ARCHITECTURE.md ss4.1), not a crash.
    evening_slot_ids = {s.id for s in slots if s.shift_type_code != "MORNING"}
    understaffed_ids = {d.slot_id for d in output.diagnostics.slot_diagnostics}
    assert evening_slot_ids <= understaffed_ids
    assert all(
        d.available_staff == 0
        for d in output.diagnostics.slot_diagnostics
        if d.slot_id in evening_slot_ids
    )
    # But mornings, which everyone wants, are fully covered.
    morning_slot_ids = {s.id for s in slots if s.shift_type_code == "MORNING"}
    assert morning_slot_ids.isdisjoint(understaffed_ids)


def test_one_person_available_only_fridays_never_placed_elsewhere() -> None:
    dates = dates_range(14)
    slots = standard_slots(dates, required=2, minimum=1, maximum=3)
    friday_only = make_employee("friday_only", contract_min=1, contract_max=18)
    others = [make_employee(f"e{i}", contract_min=3, contract_max=18) for i in range(5)]
    employees = [friday_only, *others]

    availability = available_everywhere(others, slots) + [
        AvailabilityInput(employee_id=friday_only.id, slot_id=s.id, level="AVAILABLE")
        for s in slots
        if s.date.weekday() == 4  # Friday
    ]

    inp = SolverInput(
        period_id="p",
        slots=tuple(slots),
        employees=tuple(employees),
        availability=tuple(availability),
        config=DETERMINISTIC_CONFIG,
    )
    output = solve(inp)

    assert output.status in ("OPTIMAL", "FEASIBLE")
    _assert_all_hard_rules(inp, output)
    friday_shifts = [a for a in output.assignments if a.employee_id == friday_only.id]
    slots_by_id = {s.id: s for s in slots}
    assert all(slots_by_id[a.slot_id].date.weekday() == 4 for a in friday_shifts)


def test_closed_day_removed_from_input_breaks_consecutive_day_run() -> None:
    """A holiday/closed day is simply absent from `input.slots` (the service
    layer's job, per ARCHITECTURE.md ss3.2's `ShiftSlot.is_closed`) - solve()
    itself needs no special case for it. This also proves the max-consecutive-
    days sliding window treats the gap as a real break: with max_consecutive_days=1,
    an employee preferred on day 1 and day 3 (day 2 missing) must be able to
    work both, since two isolated single days is not a 2-day run.
    """
    dates = dates_range(3)
    day1, _closed_day, day3 = dates
    slots = [make_slot(day1, MORNING), make_slot(day3, MORNING)]
    employee = make_employee("e1", contract_min=1, contract_max=18, max_consecutive_days=1)
    availability = [
        AvailabilityInput(employee_id=employee.id, slot_id=s.id, level="PREFERRED") for s in slots
    ]

    inp = SolverInput(
        period_id="p",
        slots=tuple(slots),
        employees=(employee,),
        availability=tuple(availability),
        config=DETERMINISTIC_CONFIG,
    )
    output = solve(inp)

    assert output.status in ("OPTIMAL", "FEASIBLE")
    _assert_all_hard_rules(inp, output)
    assert {a.slot_id for a in output.assignments} == {s.id for s in slots}
    assert not any(d.date == dates[1] for d in output.diagnostics.slot_diagnostics)


def test_genuinely_understaffed_month_still_returns_usable_schedule() -> None:
    """One impossible month (far too few employees for the staffing levels)
    must not cost the whole schedule - CLAUDE.md: "must NEVER return
    INFEASIBLE... fill everything it can and report the gaps."
    """
    dates = dates_range(14)
    slots = standard_slots(dates, required=3, minimum=2, maximum=4)
    employees = [make_employee(f"e{i}", contract_min=2, contract_max=18) for i in range(2)]
    availability = available_everywhere(employees, slots)

    inp = SolverInput(
        period_id="p",
        slots=tuple(slots),
        employees=tuple(employees),
        availability=tuple(availability),
        config=DETERMINISTIC_CONFIG,
    )
    output = solve(inp)

    assert output.status in ("OPTIMAL", "FEASIBLE")
    _assert_all_hard_rules(inp, output)
    assert len(output.assignments) > 0
    assert len(output.diagnostics.slot_diagnostics) > 0
    assert output.stats.understaffed_slot_count > 0


def test_no_availability_submitted_returns_coherent_empty_schedule() -> None:
    dates = dates_range(7)
    slots = standard_slots(dates)
    employees = [make_employee(f"e{i}") for i in range(4)]

    inp = SolverInput(
        period_id="p",
        slots=tuple(slots),
        employees=tuple(employees),
        availability=(),
        config=DETERMINISTIC_CONFIG,
    )
    output = solve(inp)

    assert output.status in ("OPTIMAL", "FEASIBLE")
    assert output.assignments == ()
    assert output.stats.coverage_rate == 0.0
    assert len(output.diagnostics.slot_diagnostics) == len(slots)


def test_no_employees_is_handled_without_crashing() -> None:
    dates = dates_range(7)
    slots = standard_slots(dates)

    inp = SolverInput(
        period_id="p",
        slots=tuple(slots),
        employees=(),
        availability=(),
        config=DETERMINISTIC_CONFIG,
    )
    output = solve(inp)

    assert output.status == "NO_EMPLOYEES"
    assert output.assignments == ()
    assert len(output.diagnostics.slot_diagnostics) == len(slots)


def test_period_with_no_slots_is_handled_without_crashing() -> None:
    employees = [make_employee("e1")]

    inp = SolverInput(
        period_id="p",
        slots=(),
        employees=tuple(employees),
        availability=(),
        config=DETERMINISTIC_CONFIG,
    )
    output = solve(inp)

    assert output.status == "NO_SLOTS"
    assert output.assignments == ()
    assert output.stats.total_slots == 0
    assert output.stats.coverage_rate == 1.0


def test_high_scorer_wins_a_contested_preferred_shift() -> None:
    slot = make_slot(dates_range(1)[0], EVENING, required=1, minimum=1, maximum=1)
    high = make_employee("high", contract_min=0, contract_max=18, score=95.0)
    low = make_employee("low", contract_min=0, contract_max=18, score=10.0)
    availability = [
        AvailabilityInput(employee_id=high.id, slot_id=slot.id, level="PREFERRED"),
        AvailabilityInput(employee_id=low.id, slot_id=slot.id, level="PREFERRED"),
    ]

    inp = SolverInput(
        period_id="p",
        slots=(slot,),
        employees=(high, low),
        availability=tuple(availability),
        config=DETERMINISTIC_CONFIG,
    )
    output = solve(inp)

    assert {a.employee_id for a in output.assignments} == {"high"}


def test_low_scorer_still_reaches_contract_minimum_despite_losing_contested_shifts() -> None:
    """High scorer wins every contested slot on its own, but fairness +
    contract-minimum-shortfall pressure in the objective must still get the
    low scorer to their own minimum across the month (ARCHITECTURE.md ss4.2:
    "high scorers reliably win contested desirable shifts... while everyone
    still reaches their contract minimum").
    """
    dates = dates_range(10)
    slots = standard_slots(dates, required=1, minimum=1, maximum=1)
    high = make_employee("high", contract_min=3, contract_max=18, score=95.0)
    low = make_employee("low", contract_min=3, contract_max=18, score=10.0)
    employees = [high, low]
    availability = [
        AvailabilityInput(employee_id=e.id, slot_id=s.id, level="PREFERRED")
        for e in employees
        for s in slots
    ]

    inp = SolverInput(
        period_id="p",
        slots=tuple(slots),
        employees=tuple(employees),
        availability=tuple(availability),
        config=DETERMINISTIC_CONFIG,
    )
    output = solve(inp)

    assert output.status in ("OPTIMAL", "FEASIBLE")
    _assert_all_hard_rules(inp, output)
    assert output.stats.shifts_per_employee["low"] >= low.contract_min_shifts
    assert not any(d.employee_id == "low" for d in output.diagnostics.employee_diagnostics)


def test_preference_debt_breaks_a_tie_between_equal_scorers() -> None:
    slot = make_slot(dates_range(1)[0], EVENING, required=1, minimum=1, maximum=1)
    owed = make_employee("owed", contract_min=0, contract_max=18, score=50.0, preference_debt=8)
    fresh = make_employee("fresh", contract_min=0, contract_max=18, score=50.0, preference_debt=0)
    availability = [
        AvailabilityInput(employee_id=owed.id, slot_id=slot.id, level="PREFERRED"),
        AvailabilityInput(employee_id=fresh.id, slot_id=slot.id, level="PREFERRED"),
    ]

    inp = SolverInput(
        period_id="p",
        slots=(slot,),
        employees=(owed, fresh),
        availability=tuple(availability),
        config=DETERMINISTIC_CONFIG,
    )
    output = solve(inp)

    assert {a.employee_id for a in output.assignments} == {"owed"}


def test_locked_assignment_survives_even_against_declared_unavailability() -> None:
    slot = make_slot(dates_range(1)[0], MORNING, required=1, minimum=1, maximum=1)
    employee = make_employee("e1")
    # No AvailabilityInput at all for (e1, slot) - declared/defaulted UNAVAILABLE -
    # but the manager pinned them there anyway (ARCHITECTURE.md ss3.6).
    locked = [LockedAssignmentInput(employee_id=employee.id, slot_id=slot.id)]

    inp = SolverInput(
        period_id="p",
        slots=(slot,),
        employees=(employee,),
        availability=(),
        locked_assignments=tuple(locked),
        config=DETERMINISTIC_CONFIG,
    )
    output = solve(inp)

    assert_locked_preserved(locked, output.assignments)
    assert output.assignments[0].is_locked is True


def test_conflicting_locks_never_make_the_solver_infeasible() -> None:
    """Two locked assignments for the same employee on the same day is a
    pre-existing manual violation of ONE_SHIFT_PER_DAY. The solver must not
    blow up over it - it preserves both locks and moves on.
    """
    day = dates_range(1)[0]
    morning = make_slot(day, MORNING, required=1, minimum=1, maximum=1)
    evening = make_slot(day, EVENING, required=1, minimum=1, maximum=1)
    employee = make_employee("e1")
    locked = [
        LockedAssignmentInput(employee_id=employee.id, slot_id=morning.id),
        LockedAssignmentInput(employee_id=employee.id, slot_id=evening.id),
    ]

    inp = SolverInput(
        period_id="p",
        slots=(morning, evening),
        employees=(employee,),
        availability=(),
        locked_assignments=tuple(locked),
        config=DETERMINISTIC_CONFIG,
    )
    output = solve(inp)

    assert output.status != "INFEASIBLE"
    assert_locked_preserved(locked, output.assignments)


def test_determinism_with_fixed_seed_and_single_worker() -> None:
    dates = dates_range(7)
    slots = standard_slots(dates, required=1, minimum=1, maximum=2)
    employees = [
        make_employee(f"e{i}", contract_min=2, contract_max=18, score=score)
        for i, score in enumerate([90.0, 70.0, 50.0, 30.0])
    ]
    availability = [
        AvailabilityInput(
            employee_id=e.id, slot_id=s.id, level="PREFERRED" if i % 2 == 0 else "AVAILABLE"
        )
        for i, e in enumerate(employees)
        for s in slots
    ]

    def _run() -> frozenset[tuple[str, str]]:
        inp = SolverInput(
            period_id="p",
            slots=tuple(slots),
            employees=tuple(employees),
            availability=tuple(availability),
            weights=SolverWeights(),
            config=DETERMINISTIC_CONFIG,
        )
        output = solve(inp)
        return frozenset((a.employee_id, a.slot_id) for a in output.assignments)

    assert _run() == _run()
