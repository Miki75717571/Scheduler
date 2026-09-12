"""Plain-value input/output contracts for the solver (ARCHITECTURE.md ss4).
Frozen dataclasses only - no SQLAlchemy, no ORM instances, no app.models
enums. The service layer (app/services/solver_service.py) is responsible for
turning ORM rows into these and back again; this module must stay readable
and testable with nothing but fixture literals.

`AVAILABLE`/`PREFERRED` are the only availability levels carried in - absence
of an AvailabilityInput row for an (employee, slot) pair means UNAVAILABLE,
mirroring the storage convention in app/models/availability.py.
"""

from dataclasses import dataclass, field
from datetime import date, time
from typing import Literal

AvailabilityLevel = Literal["AVAILABLE", "PREFERRED"]


@dataclass(frozen=True)
class EmployeeInput:
    id: str
    full_name: str
    contract_min_shifts: int
    contract_max_shifts: int
    max_consecutive_days: int
    min_rest_hours: int
    # 0-100 composite (ARCHITECTURE.md ss3.4); None if the employee has no
    # computable composite yet (missing ratings on some active criterion) -
    # treated as 0 in the objective, never as a reason to skip the employee.
    score: float | None
    preference_debt: int = 0


@dataclass(frozen=True)
class SlotInput:
    id: str
    date: date
    shift_type_code: str
    start_time: time
    end_time: time
    required_staff: int
    min_staff: int
    max_staff: int
    is_weekend: bool


@dataclass(frozen=True)
class AvailabilityInput:
    employee_id: str
    slot_id: str
    level: AvailabilityLevel


@dataclass(frozen=True)
class LockedAssignmentInput:
    """A manager-pinned (employee, slot) pair from a prior run/manual edit.
    Always forced into the solution regardless of declared availability -
    see ARCHITECTURE.md ss3.6's `is_locked`.
    """

    employee_id: str
    slot_id: str


@dataclass(frozen=True)
class SolverWeights:
    """ARCHITECTURE.md ss4.1's objective coefficients. Defaults match the
    doc exactly; the live values normally come from the `solver_weight_configs`
    DB row (app/models/solver_weight_config.py) so they're tunable without a
    deploy, but this dataclass itself has no idea where they came from.
    """

    understaffing: int = 10000
    contract_min_shortfall: int = 1000
    denied_preference: int = 20
    fairness_spread: int = 30
    unpopular_shift_spread: int = 25
    score_weight: int = 10
    preference_debt: int = 15


@dataclass(frozen=True)
class SolverConfig:
    time_limit_seconds: float = 30.0
    random_seed: int = 42
    # Tests pin this to 1 for determinism (CLAUDE.md "Tests"); production
    # leaves it at the OR-Tools default (0 = use all cores) since the problem
    # size here (~25 employees x ~70 slots) doesn't need it.
    num_search_workers: int = 8


@dataclass(frozen=True)
class SolverInput:
    period_id: str
    slots: tuple[SlotInput, ...]
    employees: tuple[EmployeeInput, ...]
    availability: tuple[AvailabilityInput, ...]
    locked_assignments: tuple[LockedAssignmentInput, ...] = ()
    weights: SolverWeights = field(default_factory=SolverWeights)
    config: SolverConfig = field(default_factory=SolverConfig)


@dataclass(frozen=True)
class AssignmentOutput:
    employee_id: str
    slot_id: str
    is_locked: bool


@dataclass(frozen=True)
class SlotDiagnostic:
    """One human-readable red-tile explanation - only emitted for slots that
    are actually understaffed (ARCHITECTURE.md ss4.1's "the solver's failure
    output becomes the feature").
    """

    slot_id: str
    date: date
    shift_type_code: str
    required_staff: int
    min_staff: int
    assigned_staff: int
    available_staff: int
    message_key: str
    message_params: dict[str, object]


@dataclass(frozen=True)
class EmployeeDiagnostic:
    """Emitted only for employees who land below their contract minimum."""

    employee_id: str
    assigned_count: int
    contract_min_shifts: int
    shortfall: int
    declared_count: int
    message_key: str
    message_params: dict[str, object]


@dataclass(frozen=True)
class Diagnostics:
    slot_diagnostics: tuple[SlotDiagnostic, ...]
    employee_diagnostics: tuple[EmployeeDiagnostic, ...]


@dataclass(frozen=True)
class SolverStats:
    total_slots: int
    total_required_staff: int
    total_assigned: int
    understaffed_slot_count: int
    coverage_rate: float  # total_assigned / total_required_staff, 1.0 if no staff required
    # granted / declared PREFERRED assignments; None if nobody declared PREFERRED at all
    preference_satisfaction_rate: float | None
    fairness_spread: int  # max workload - min workload across employees
    shifts_per_employee: dict[str, int]


@dataclass(frozen=True)
class SolverOutput:
    # OPTIMAL | FEASIBLE | INFEASIBLE_FALLBACK | NO_EMPLOYEES | NO_SLOTS
    status: str
    objective_value: float | None
    assignments: tuple[AssignmentOutput, ...]
    diagnostics: Diagnostics
    stats: SolverStats
    solve_time_ms: int
