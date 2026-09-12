import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.score_criterion import ScoreCriterion


class ScoreCriterionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, criterion_id: uuid.UUID) -> ScoreCriterion | None:
        return await self._db.get(ScoreCriterion, criterion_id)

    async def get_by_code(self, code: str) -> ScoreCriterion | None:
        result = await self._db.execute(select(ScoreCriterion).where(ScoreCriterion.code == code))
        return result.scalar_one_or_none()

    async def list_all(self, *, active_only: bool = False) -> list[ScoreCriterion]:
        stmt = select(ScoreCriterion).order_by(ScoreCriterion.name_en)
        if active_only:
            stmt = stmt.where(ScoreCriterion.is_active.is_(True))
        result = await self._db.execute(stmt)
        return list(result.scalars())

    async def list_by_ids(self, criterion_ids: set[uuid.UUID]) -> list[ScoreCriterion]:
        if not criterion_ids:
            return []
        result = await self._db.execute(
            select(ScoreCriterion).where(ScoreCriterion.id.in_(criterion_ids))
        )
        return list(result.scalars())

    async def create(self, criterion: ScoreCriterion) -> ScoreCriterion:
        self._db.add(criterion)
        await self._db.flush()
        return criterion

    async def save(self, criterion: ScoreCriterion) -> ScoreCriterion:
        await self._db.flush()
        return criterion
