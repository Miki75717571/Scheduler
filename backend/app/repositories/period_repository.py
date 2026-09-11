import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule_period import SchedulePeriod


class PeriodRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, period_id: uuid.UUID) -> SchedulePeriod | None:
        return await self._db.get(SchedulePeriod, period_id)

    async def get_by_year_month(self, year: int, month: int) -> SchedulePeriod | None:
        result = await self._db.execute(
            select(SchedulePeriod).where(SchedulePeriod.year == year, SchedulePeriod.month == month)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[SchedulePeriod]:
        result = await self._db.execute(
            select(SchedulePeriod).order_by(SchedulePeriod.year.desc(), SchedulePeriod.month.desc())
        )
        return list(result.scalars())

    async def create(self, period: SchedulePeriod) -> SchedulePeriod:
        self._db.add(period)
        await self._db.flush()
        return period

    async def save(self, period: SchedulePeriod) -> SchedulePeriod:
        await self._db.flush()
        return period
