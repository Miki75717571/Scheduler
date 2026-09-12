"""Solver identity and (de)serialization helpers for SolverWeights.

`ALGORITHM_VERSION` is snapshotted onto every ScheduleRun row so a manager
comparing two runs (or a future insights page, ARCHITECTURE.md ss4.3) can
tell whether a difference came from changed input or a changed model.
Bump it whenever cpsat.py's formulation changes in a way that could move the
objective value for the same input.
"""

from dataclasses import asdict
from typing import Any

from app.scheduling.domain import SolverWeights

ALGORITHM_VERSION = "cpsat-v1"

_FIELDS = tuple(SolverWeights.__dataclass_fields__)


def weights_to_dict(weights: SolverWeights) -> dict[str, int]:
    return asdict(weights)


def weights_from_dict(data: dict[str, Any]) -> SolverWeights:
    """Builds a SolverWeights from a plain dict (a DB row's columns, or a
    ScheduleRun.params_snapshot blob), ignoring unknown keys and falling back
    to the dataclass default for any missing one so an old snapshot missing a
    newly-added weight still loads.
    """
    known = {key: int(data[key]) for key in _FIELDS if key in data}
    return SolverWeights(**known)
