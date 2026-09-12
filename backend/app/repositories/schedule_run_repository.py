import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule_run import ScheduleRun


class ScheduleRunRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, run_id: uuid.UUID) -> ScheduleRun | None:
        return await self._db.get(ScheduleRun, run_id)

    async def list_by_period(self, period_id: uuid.UUID) -> list[ScheduleRun]:
        result = await self._db.execute(
            select(ScheduleRun)
            .where(ScheduleRun.period_id == period_id)
            .order_by(ScheduleRun.created_at.desc())
        )
        return list(result.scalars())

    async def create(self, run: ScheduleRun) -> ScheduleRun:
        self._db.add(run)
        await self._db.flush()
        return run

    async def save(self, run: ScheduleRun) -> ScheduleRun:
        await self._db.flush()
        return run
