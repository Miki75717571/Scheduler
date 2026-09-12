from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.solver_weight_config import SolverWeightConfig


class SolverWeightConfigRepository:
    """Single-row config table (app/models/solver_weight_config.py's
    docstring explains why it isn't versioned like EmployeeScore).
    `get_or_create_default` is the only read path so callers never have to
    special-case "nobody has configured this yet" - a migration seeds one row
    already, but this stays safe even against a database that predates it.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_or_create_default(self) -> SolverWeightConfig:
        result = await self._db.execute(select(SolverWeightConfig).limit(1))
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        config = SolverWeightConfig()
        self._db.add(config)
        await self._db.flush()
        return config

    async def save(self, config: SolverWeightConfig) -> SolverWeightConfig:
        await self._db.flush()
        return config
