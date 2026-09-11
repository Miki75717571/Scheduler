import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shift_slot import ShiftSlot


class ShiftSlotRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, slot_id: uuid.UUID) -> ShiftSlot | None:
        return await self._db.get(ShiftSlot, slot_id)

    async def get_many(self, slot_ids: Iterable[uuid.UUID]) -> list[ShiftSlot]:
        ids = list(slot_ids)
        if not ids:
            return []
        result = await self._db.execute(select(ShiftSlot).where(ShiftSlot.id.in_(ids)))
        return list(result.scalars())

    async def list_by_period(self, period_id: uuid.UUID) -> list[ShiftSlot]:
        result = await self._db.execute(
            select(ShiftSlot).where(ShiftSlot.period_id == period_id).order_by(ShiftSlot.date)
        )
        return list(result.scalars())

    async def create_many(self, slots: list[ShiftSlot]) -> None:
        self._db.add_all(slots)
        await self._db.flush()

    async def save(self, slot: ShiftSlot) -> ShiftSlot:
        await self._db.flush()
        return slot
