"""Pure scheduling domain and solver.

No sqlalchemy, app.models, or app.db imports allowed anywhere under this
package - see tests/scheduling/test_purity.py, which enforces it. Everything
here operates on plain data (frozen dataclasses in `domain.py`) so the solver
can be unit-tested, replayed, and swapped without touching the app.
"""

from app.scheduling.cpsat import solve
from app.scheduling.domain import (
    AssignmentOutput,
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
    SolverWeights,
    UnusedAvailableEmployee,
)
from app.scheduling.weights import ALGORITHM_VERSION, weights_from_dict, weights_to_dict

__all__ = [
    "ALGORITHM_VERSION",
    "AssignmentOutput",
    "AvailabilityInput",
    "AvailabilityLevel",
    "Diagnostics",
    "EmployeeDiagnostic",
    "EmployeeInput",
    "LockedAssignmentInput",
    "SlotDiagnostic",
    "SlotInput",
    "SolverConfig",
    "SolverInput",
    "SolverOutput",
    "SolverStats",
    "SolverWeights",
    "UnusedAvailableEmployee",
    "solve",
    "weights_from_dict",
    "weights_to_dict",
]
