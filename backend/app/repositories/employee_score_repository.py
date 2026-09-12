import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee_score import EmployeeScore


class EmployeeScoreRepository:
    """All DB access for scores. Unlike UserRepository, there is no
    employee-safe accessor here at all - CLAUDE.md's privacy requirement
    ("no employee-facing endpoint may return any score") is enforced by
    every route that reaches this repository requiring MANAGER/ADMIN
    (app/api/v1/scores.py's `require_role`), not by filtering rows per
    caller. Never add a method here that an employee-facing route could call.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, score: EmployeeScore) -> EmployeeScore:
        self._db.add(score)
        await self._db.flush()
        return score

    async def list_effective_rows(
        self, user_ids: set[uuid.UUID], *, as_of: date
    ) -> list[EmployeeScore]:
        """Every score row on or before `as_of` for these users, ordered so
        that the first row encountered per (user_id, criterion_id) while
        iterating is the currently-effective one. Picking "latest per group"
        in Python rather than SQL (DISTINCT ON is Postgres-only, and a
        portable window-function equivalent would need row_number() dialect
        handling anyway) keeps this identical on SQLite and Postgres.
        """
        if not user_ids:
            return []
        stmt = (
            select(EmployeeScore)
            .where(EmployeeScore.user_id.in_(user_ids), EmployeeScore.effective_from <= as_of)
            .order_by(
                EmployeeScore.user_id,
                EmployeeScore.criterion_id,
                EmployeeScore.effective_from.desc(),
                EmployeeScore.created_at.desc(),
            )
        )
        result = await self._db.execute(stmt)
        return list(result.scalars())

    async def list_history_for_user(self, user_id: uuid.UUID) -> list[EmployeeScore]:
        """Every score row ever set for this user, across all criteria and
        time - the raw material for the "changed from X to Y" timeline
        (app/services/score_service.py.get_history diffs consecutive rows
        per criterion).
        """
        stmt = (
            select(EmployeeScore)
            .where(EmployeeScore.user_id == user_id)
            .order_by(
                EmployeeScore.criterion_id,
                EmployeeScore.effective_from.desc(),
                EmployeeScore.created_at.desc(),
            )
        )
        result = await self._db.execute(stmt)
        return list(result.scalars())
