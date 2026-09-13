import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shift_type import ShiftType
from app.models.shift_type_weekday_override import ShiftTypeWeekdayOverride
from app.rules.weekdays import Weekday


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

    # --- per-weekday overrides ------------------------------------------

    async def list_overrides(self, shift_type_id: uuid.UUID) -> list[ShiftTypeWeekdayOverride]:
        result = await self._db.execute(
            select(ShiftTypeWeekdayOverride).where(
                ShiftTypeWeekdayOverride.shift_type_id == shift_type_id
            )
        )
        return list(result.scalars())

    async def list_overrides_for_types(
        self, shift_type_ids: Iterable[uuid.UUID]
    ) -> list[ShiftTypeWeekdayOverride]:
        ids = list(shift_type_ids)
        if not ids:
            return []
        result = await self._db.execute(
            select(ShiftTypeWeekdayOverride).where(ShiftTypeWeekdayOverride.shift_type_id.in_(ids))
        )
        return list(result.scalars())

    async def get_override(
        self, shift_type_id: uuid.UUID, weekday: Weekday
    ) -> ShiftTypeWeekdayOverride | None:
        result = await self._db.execute(
            select(ShiftTypeWeekdayOverride).where(
                ShiftTypeWeekdayOverride.shift_type_id == shift_type_id,
                ShiftTypeWeekdayOverride.weekday == weekday,
            )
        )
        return result.scalar_one_or_none()

    async def save_override(self, override: ShiftTypeWeekdayOverride) -> ShiftTypeWeekdayOverride:
        self._db.add(override)
        await self._db.flush()
        return override

    async def delete_override(self, override: ShiftTypeWeekdayOverride) -> None:
        await self._db.delete(override)
        await self._db.flush()
