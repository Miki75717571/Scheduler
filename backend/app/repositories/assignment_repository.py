import uuid
from collections.abc import Iterable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignment import Assignment
from app.models.shift_slot import ShiftSlot


class AssignmentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, assignment_id: uuid.UUID) -> Assignment | None:
        return await self._db.get(Assignment, assignment_id)

    async def get_by_slot_and_user(
        self, shift_slot_id: uuid.UUID, user_id: uuid.UUID
    ) -> Assignment | None:
        result = await self._db.execute(
            select(Assignment).where(
                Assignment.shift_slot_id == shift_slot_id, Assignment.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def list_by_period(self, period_id: uuid.UUID) -> list[Assignment]:
        result = await self._db.execute(
            select(Assignment)
            .join(ShiftSlot, ShiftSlot.id == Assignment.shift_slot_id)
            .where(ShiftSlot.period_id == period_id)
        )
        return list(result.scalars())

    async def list_by_slot(self, shift_slot_id: uuid.UUID) -> list[Assignment]:
        result = await self._db.execute(
            select(Assignment).where(Assignment.shift_slot_id == shift_slot_id)
        )
        return list(result.scalars())

    async def list_by_slots(self, shift_slot_ids: Iterable[uuid.UUID]) -> list[Assignment]:
        ids = list(shift_slot_ids)
        if not ids:
            return []
        result = await self._db.execute(select(Assignment).where(Assignment.shift_slot_id.in_(ids)))
        return list(result.scalars())

    async def list_by_user_and_period(
        self, user_id: uuid.UUID, period_id: uuid.UUID
    ) -> list[Assignment]:
        result = await self._db.execute(
            select(Assignment)
            .join(ShiftSlot, ShiftSlot.id == Assignment.shift_slot_id)
            .where(ShiftSlot.period_id == period_id, Assignment.user_id == user_id)
        )
        return list(result.scalars())

    async def delete_non_locked_by_period(self, period_id: uuid.UUID) -> None:
        """Wipes every non-locked assignment for a period in one statement -
        used by app/services/solver_service.py before writing a fresh solver
        run's output, so regeneration replaces exactly the assignments the
        manager hasn't pinned (ARCHITECTURE.md ss3.6's `is_locked`).
        """
        slot_ids = select(ShiftSlot.id).where(ShiftSlot.period_id == period_id)
        await self._db.execute(
            delete(Assignment).where(
                Assignment.shift_slot_id.in_(slot_ids), Assignment.is_locked.is_(False)
            )
        )

    async def create(self, assignment: Assignment) -> Assignment:
        self._db.add(assignment)
        await self._db.flush()
        return assignment

    async def save(self, assignment: Assignment) -> Assignment:
        await self._db.flush()
        return assignment

    async def delete(self, assignment: Assignment) -> None:
        await self._db.delete(assignment)
        await self._db.flush()
