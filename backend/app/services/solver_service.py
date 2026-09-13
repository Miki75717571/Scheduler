"""The impure half of Phase 5: turns DB rows into a SolverInput, runs the
pure solver off the event loop, and writes a SolverOutput back as
Assignment/ScheduleRun rows. Nothing in app/scheduling/ is imported here for
its side effects - only `solve()` and the plain dataclasses/helpers it
exports (ARCHITECTURE.md ss1's "solver must be a pure function").

`execute_run` is meant to run from a background task (app/api/v1's router),
never inside a request handler - see CLAUDE.md "Running it". It never lets
an exception escape: any failure is captured onto the ScheduleRun row as
FAILED instead, since nothing is listening on the other end of a background
task to report it.
"""

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignment import Assignment, AssignmentSource
from app.models.audit_log import AuditLog
from app.models.rule import Rule, RulePhase, RuleScope, RuleType
from app.models.schedule_period import PeriodState, SchedulePeriod
from app.models.schedule_run import ScheduleRun, ScheduleRunStatus
from app.models.shift_slot import ShiftSlot
from app.models.shift_type import ShiftType
from app.models.user import Role, User
from app.repositories.assignment_repository import AssignmentRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.availability_repository import AvailabilityRepository
from app.repositories.period_repository import PeriodRepository
from app.repositories.rule_repository import RuleRepository
from app.repositories.schedule_run_repository import ScheduleRunRepository
from app.repositories.shift_slot_repository import ShiftSlotRepository
from app.repositories.shift_type_repository import ShiftTypeRepository
from app.repositories.solver_weight_config_repository import SolverWeightConfigRepository
from app.repositories.user_repository import UserRepository
from app.rules.weekdays import is_weekend
from app.scheduling import (
    ALGORITHM_VERSION,
    AvailabilityInput,
    AvailabilityLevel,
    Diagnostics,
    EmployeeDiagnostic,
    EmployeeInput,
    LockedAssignmentInput,
    SlotDiagnostic,
    SlotInput,
    SolverConfig,
    SolverInput,
    SolverOutput,
    SolverStats,
    solve,
    weights_from_dict,
    weights_to_dict,
)
from app.services.score_service import ScoreService

_RUNNABLE_STATES = (PeriodState.LOCKED, PeriodState.GENERATED)

# Fallbacks when neither a per-employee override nor an applicable Rule row
# configures these - "no requirement" / "no cap" rather than an invented
# number, so an unconfigured shop never silently gets rules it never set up.
_DEFAULT_CONTRACT_MIN = 0
_DEFAULT_CONTRACT_MAX = 31
_DEFAULT_MAX_CONSECUTIVE_DAYS = 31
_DEFAULT_MIN_REST_HOURS = 0

_DEFAULT_TIME_LIMIT_SECONDS = 30.0


class SolverError(Exception):
    def __init__(self, message_key: str, params: dict[str, Any] | None = None) -> None:
        self.message_key = message_key
        self.params = params or {}
        super().__init__(message_key)


def _rule_applies_to(rule: Rule, user: User) -> bool:
    """Duplicated, deliberately, from schedule_service.py's private helper of
    the same name - ARCHITECTURE.md ss3.5 already establishes that the
    solver and the validator each get their own copy of scope-resolution
    logic rather than sharing a module, since they answer different
    questions ("what should I aim for" vs "what actually holds right now").
    """
    if rule.scope == RuleScope.GLOBAL:
        return True
    if rule.scope == RuleScope.USER:
        return rule.scope_ref == str(user.id)
    if rule.scope == RuleScope.EMPLOYMENT_TYPE:
        return user.employment_type is not None and rule.scope_ref == user.employment_type.value
    return False


_SCOPE_SPECIFICITY = {RuleScope.USER: 0, RuleScope.EMPLOYMENT_TYPE: 1, RuleScope.GLOBAL: 2}


def _rule_param_for_user(
    rules: list[Rule], user: User, rule_type: RuleType, param_key: str
) -> int | None:
    applicable = [r for r in rules if r.type == rule_type and _rule_applies_to(r, user)]
    if not applicable:
        return None
    applicable.sort(key=lambda r: _SCOPE_SPECIFICITY[r.scope])
    return int(applicable[0].params[param_key])


def _resolve_employee_input(user: User, rules: list[Rule], *, score: float | None) -> EmployeeInput:
    contract_min = user.contract_min_shifts
    if contract_min is None:
        contract_min = (
            _rule_param_for_user(rules, user, RuleType.MIN_SHIFTS_PER_MONTH, "n")
            or _DEFAULT_CONTRACT_MIN
        )
    contract_max = user.contract_max_shifts
    if contract_max is None:
        contract_max = (
            _rule_param_for_user(rules, user, RuleType.MAX_SHIFTS_PER_MONTH, "n")
            or _DEFAULT_CONTRACT_MAX
        )
    max_consecutive_days = (
        _rule_param_for_user(rules, user, RuleType.MAX_CONSECUTIVE_DAYS, "n")
        or _DEFAULT_MAX_CONSECUTIVE_DAYS
    )
    min_rest_hours = (
        _rule_param_for_user(rules, user, RuleType.MIN_REST_HOURS, "h") or _DEFAULT_MIN_REST_HOURS
    )
    return EmployeeInput(
        id=str(user.id),
        full_name=user.full_name,
        contract_min_shifts=contract_min,
        contract_max_shifts=contract_max,
        max_consecutive_days=max_consecutive_days,
        min_rest_hours=min_rest_hours,
        score=score,
        preference_debt=user.preference_debt,
    )


def _assignment_snapshot(assignment: Assignment) -> dict[str, Any]:
    return {
        "shift_slot_id": str(assignment.shift_slot_id),
        "user_id": str(assignment.user_id),
        "source": assignment.source.value,
        "is_locked": assignment.is_locked,
    }


def _slot_diagnostic_to_json(diagnostic: SlotDiagnostic) -> dict[str, Any]:
    return {
        "slot_id": diagnostic.slot_id,
        "date": diagnostic.date.isoformat(),
        "shift_type_code": diagnostic.shift_type_code,
        "required_staff": diagnostic.required_staff,
        "min_staff": diagnostic.min_staff,
        "assigned_staff": diagnostic.assigned_staff,
        "available_staff": diagnostic.available_staff,
        "message_key": diagnostic.message_key,
        "message_params": diagnostic.message_params,
        "unused_available": [asdict(u) for u in diagnostic.unused_available],
    }


def _employee_diagnostic_to_json(diagnostic: EmployeeDiagnostic) -> dict[str, Any]:
    return asdict(diagnostic)


def _diagnostics_to_json(diagnostics: Diagnostics) -> dict[str, Any]:
    return {
        "slots": [_slot_diagnostic_to_json(d) for d in diagnostics.slot_diagnostics],
        "employees": [_employee_diagnostic_to_json(d) for d in diagnostics.employee_diagnostics],
    }


def _stats_to_json(stats: SolverStats) -> dict[str, Any]:
    return asdict(stats)


class SolverService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._runs = ScheduleRunRepository(db)
        self._periods = PeriodRepository(db)
        self._slots = ShiftSlotRepository(db)
        self._shift_types = ShiftTypeRepository(db)
        self._users = UserRepository(db)
        self._availability = AvailabilityRepository(db)
        self._assignments = AssignmentRepository(db)
        self._rules = RuleRepository(db)
        self._weight_config = SolverWeightConfigRepository(db)
        self._audit_log = AuditLogRepository(db)

    # --- creating a run (cheap, safe to call inside a request handler) ----

    async def create_run(
        self, period: SchedulePeriod, *, actor: User, time_limit_seconds: float | None = None
    ) -> ScheduleRun:
        if period.state not in _RUNNABLE_STATES:
            raise SolverError("schedule_run.period_not_ready", {"state": period.state.value})

        weight_config = await self._weight_config.get_or_create_default()
        weights = weights_from_dict(
            {
                "understaffing": weight_config.understaffing,
                "contract_min_shortfall": weight_config.contract_min_shortfall,
                "denied_preference": weight_config.denied_preference,
                "fairness_spread": weight_config.fairness_spread,
                "unpopular_shift_spread": weight_config.unpopular_shift_spread,
                "score_weight": weight_config.score_weight,
                "preference_debt": weight_config.preference_debt,
            }
        )
        default_config = SolverConfig()
        snapshot = {
            "weights": weights_to_dict(weights),
            "time_limit_seconds": time_limit_seconds or _DEFAULT_TIME_LIMIT_SECONDS,
            "random_seed": default_config.random_seed,
            "num_search_workers": default_config.num_search_workers,
        }

        # Taken now, before the solve even starts - "revert" always means
        # "undo this run", not "undo whatever the DB happens to look like
        # when the button is clicked" (CLAUDE.md's "protect my manual work").
        existing_assignments = await self._assignments.list_by_period(period.id)
        pre_run_snapshot = [_assignment_snapshot(a) for a in existing_assignments]

        run = ScheduleRun(
            period_id=period.id,
            status=ScheduleRunStatus.PENDING,
            algorithm_version=ALGORITHM_VERSION,
            params_snapshot=snapshot,
            pre_run_snapshot=pre_run_snapshot,
            created_by_user_id=actor.id,
        )
        await self._runs.create(run)
        await self._db.commit()
        await self._db.refresh(run)
        return run

    async def get_run(self, run_id: uuid.UUID) -> ScheduleRun:
        run = await self._runs.get_by_id(run_id)
        if run is None:
            raise SolverError("schedule_run.not_found")
        return run

    async def list_runs(self, period: SchedulePeriod) -> list[ScheduleRun]:
        return await self._runs.list_by_period(period.id)

    async def revert_run(self, run_id: uuid.UUID, *, actor: User) -> ScheduleRun:
        """Restores the period's assignments to exactly what they were right
        before this run was created (`pre_run_snapshot`), undoing whatever
        the run itself (and anything since) did. One-click, per CLAUDE.md -
        deliberately a full restore rather than a diff/merge, so it is
        trivial to reason about what "revert" means.
        """
        run = await self.get_run(run_id)
        if run.status != ScheduleRunStatus.SUCCESS:
            raise SolverError("schedule_run.not_revertible")
        if run.pre_run_snapshot is None:
            raise SolverError("schedule_run.no_snapshot")
        if run.reverted_at is not None:
            raise SolverError("schedule_run.already_reverted")

        period = await self._periods.get_by_id(run.period_id)
        if period is None:
            raise SolverError("period.not_found")

        await self._assignments.delete_all_by_period(period.id)
        for entry in run.pre_run_snapshot:
            self._db.add(
                Assignment(
                    shift_slot_id=uuid.UUID(entry["shift_slot_id"]),
                    user_id=uuid.UUID(entry["user_id"]),
                    source=AssignmentSource(entry["source"]),
                    is_locked=entry["is_locked"],
                    created_by_user_id=actor.id,
                    modified_after_publish=period.state == PeriodState.PUBLISHED,
                )
            )
        await self._db.flush()

        run.reverted_at = datetime.now(UTC)
        run.reverted_by_user_id = actor.id
        await self._runs.save(run)
        await self._audit_log.create(
            AuditLog(
                actor_user_id=actor.id,
                period_id=period.id,
                action="schedule_run.revert",
                entity_type="ScheduleRun",
                entity_id=run.id,
                before=None,
                after={"restored_assignments": len(run.pre_run_snapshot)},
            )
        )
        await self._db.commit()
        await self._db.refresh(run)
        return run

    # --- building the pure input --------------------------------------------

    async def _build_input(self, period: SchedulePeriod, run: ScheduleRun) -> SolverInput:
        all_slots = await self._slots.list_by_period(period.id)
        open_slots = [s for s in all_slots if not s.is_closed]
        shift_types_by_id = {st.id: st for st in await self._shift_types.list_all()}
        # Unlike schedule_service.py's validator (which checks *any* active
        # user's manual assignments, since a manager could in principle be
        # dragged onto a shift by hand), the solver only ever proposes
        # EMPLOYEE-role accounts - auto-assigning a manager/admin account to
        # a shift it never asked for would be a surprising, not a helpful,
        # default.
        active_users = [
            u for u in await self._users.list_all() if u.is_active and u.role == Role.EMPLOYEE
        ]
        schedule_rules = await self._rules.list_active_by_phase(RulePhase.SCHEDULE)

        slot_inputs = tuple(
            self._to_slot_input(slot, shift_types_by_id[slot.shift_type_id]) for slot in open_slots
        )

        open_slot_ids = {s.id for s in open_slots}
        availability_rows = await self._availability.list_entries_for_slots(open_slot_ids)
        availability_inputs = tuple(
            AvailabilityInput(
                employee_id=str(user_id),
                slot_id=str(slot_id),
                level=cast(AvailabilityLevel, status.value),
            )
            for user_id, slot_id, status in availability_rows
            if slot_id in open_slot_ids
        )

        existing_assignments = await self._assignments.list_by_period(period.id)
        locked_inputs = tuple(
            LockedAssignmentInput(employee_id=str(a.user_id), slot_id=str(a.shift_slot_id))
            for a in existing_assignments
            if a.is_locked and a.shift_slot_id in open_slot_ids
        )

        score_rows = await ScoreService(self._db).get_grid(active_users)
        composite_by_user = {row.user_id: row.composite for row in score_rows}

        employee_inputs = tuple(
            _resolve_employee_input(user, schedule_rules, score=composite_by_user.get(user.id))
            for user in active_users
        )

        weights = weights_from_dict(run.params_snapshot["weights"])
        config = SolverConfig(
            time_limit_seconds=run.params_snapshot["time_limit_seconds"],
            random_seed=run.params_snapshot["random_seed"],
            num_search_workers=run.params_snapshot["num_search_workers"],
        )

        return SolverInput(
            period_id=str(period.id),
            slots=slot_inputs,
            employees=employee_inputs,
            availability=availability_inputs,
            locked_assignments=locked_inputs,
            weights=weights,
            config=config,
        )

    @staticmethod
    def _to_slot_input(slot: ShiftSlot, shift_type: ShiftType) -> SlotInput:
        return SlotInput(
            id=str(slot.id),
            date=slot.date,
            shift_type_code=shift_type.code,
            start_time=shift_type.start_time,
            end_time=shift_type.end_time,
            required_staff=slot.required_staff,
            min_staff=slot.min_staff,
            max_staff=slot.max_staff,
            is_weekend=is_weekend(slot.date),
        )

    # --- persisting the pure output -----------------------------------------

    async def _persist_output(
        self,
        period: SchedulePeriod,
        solver_input: SolverInput,
        output: SolverOutput,
        *,
        actor_id: uuid.UUID,
    ) -> None:
        await self._assignments.delete_non_locked_by_period(period.id)

        created = 0
        for assignment_output in output.assignments:
            if assignment_output.is_locked:
                continue  # already exists in the DB, untouched
            self._db.add(
                Assignment(
                    shift_slot_id=uuid.UUID(assignment_output.slot_id),
                    user_id=uuid.UUID(assignment_output.employee_id),
                    source=AssignmentSource.AUTO,
                    is_locked=False,
                    created_by_user_id=actor_id,
                    modified_after_publish=period.state == PeriodState.PUBLISHED,
                )
            )
            created += 1
        await self._db.flush()

        await self._apply_preference_debt(solver_input, output)

        await self._audit_log.create(
            AuditLog(
                actor_user_id=actor_id,
                period_id=period.id,
                action="schedule_run.generate",
                entity_type="SchedulePeriod",
                entity_id=period.id,
                before=None,
                after={
                    "assignments_created": created,
                    "objective_value": output.objective_value,
                    "solver_status": output.status,
                },
            )
        )

    async def _apply_preference_debt(self, solver_input: SolverInput, output: SolverOutput) -> None:
        """+1 for every declared PREFERRED slot that went unfilled by that
        employee, -1 for every one that was granted (ARCHITECTURE.md ss4.2).
        Applied once per successful run. Known simplification: regenerating
        the same period multiple times before publishing applies the delta
        each time, not just once for the period - worth revisiting (e.g.
        finalizing only at publish) once the generate screen exists.
        """
        assigned_pairs = {(a.employee_id, a.slot_id) for a in output.assignments}
        delta_by_employee: dict[str, int] = {}
        for entry in solver_input.availability:
            if entry.level != "PREFERRED":
                continue
            granted = (entry.employee_id, entry.slot_id) in assigned_pairs
            delta_by_employee[entry.employee_id] = delta_by_employee.get(entry.employee_id, 0) + (
                -1 if granted else 1
            )
        for employee_id, delta in delta_by_employee.items():
            user = await self._users.get_by_id(employee_id)
            if user is None:
                continue
            user.preference_debt += delta
            await self._users.save(user)

    # --- executing a run (background task only) -----------------------------

    async def execute_run(self, run_id: uuid.UUID) -> None:
        run = await self._runs.get_by_id(run_id)
        if run is None:
            return

        run.status = ScheduleRunStatus.RUNNING
        run.started_at = datetime.now(UTC)
        await self._runs.save(run)
        await self._db.commit()

        try:
            period = await self._periods.get_by_id(run.period_id)
            if period is None:
                raise SolverError("period.not_found")

            solver_input = await self._build_input(period, run)
            output = await asyncio.to_thread(solve, solver_input)

            await self._persist_output(
                period, solver_input, output, actor_id=run.created_by_user_id
            )

            run.status = ScheduleRunStatus.SUCCESS
            run.objective_value = output.objective_value
            run.solve_time_ms = output.solve_time_ms
            run.solver_status = output.status
            run.stats = _stats_to_json(output.stats)
            run.diagnostics = _diagnostics_to_json(output.diagnostics)
        except Exception as exc:  # noqa: BLE001 - captured onto the row, not swallowed
            run.status = ScheduleRunStatus.FAILED
            run.error_message = str(exc)[:2000]
        finally:
            run.finished_at = datetime.now(UTC)
            await self._runs.save(run)
            await self._db.commit()


async def run_solver_in_background(
    run_id: uuid.UUID, session_factory: Callable[[], AsyncSession]
) -> None:
    """Entry point for FastAPI's BackgroundTasks. Opens its own session via
    `session_factory` (app/db/session.py's `get_session_factory`, injected by
    the router) rather than importing a module-level sessionmaker directly -
    the request's own session is already closed by the time a background
    task runs (CLAUDE.md "Running it": never solve inside the request
    handler), and a hardcoded sessionmaker would always point at the
    dev/prod database even under test.
    """
    async with session_factory() as db:
        await SolverService(db).execute_run(run_id)
