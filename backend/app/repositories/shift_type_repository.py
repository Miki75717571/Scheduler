import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shift_type import ShiftType


class ShiftTypeRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, shift_type_id: uuid.UUID) -> ShiftType | None:
        return await self._db.get(ShiftType, shift_type_id)

    async def get_by_code(self, code: str) -> ShiftType | None:
        result = await self._db.execute(select(ShiftType).where(ShiftType.code == code))
        return result.scalar_one_or_none()

    async def list_all(self, *, active_only: bool = False) -> list[ShiftType]:
        stmt = select(ShiftType).order_by(ShiftType.sort_order, ShiftType.code)
        if active_only:
            stmt = stmt.where(ShiftType.is_active.is_(True))
        result = await self._db.execute(stmt)
        return list(result.scalars())

    async def create(self, shift_type: ShiftType) -> ShiftType:
        self._db.add(shift_type)
        await self._db.flush()
        return shift_type

    async def save(self, shift_type: ShiftType) -> ShiftType:
        await self._db.flush()
        return shift_type
