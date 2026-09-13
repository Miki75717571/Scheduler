import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shift_type import ShiftType
from app.models.shift_type_weekday_override import ShiftTypeWeekdayOverride
from app.repositories.shift_type_repository import ShiftTypeRepository
from app.rules.weekdays import Weekday
from app.schemas.shift_type import (
    ShiftTypeCreate,
    ShiftTypeRead,
    ShiftTypeUpdate,
    ShiftTypeWeekdayOverrideRead,
    ShiftTypeWeekdayOverrideWrite,
)


class ShiftTypeError(Exception):
    def __init__(self, message_key: str) -> None:
        self.message_key = message_key
        super().__init__(message_key)


def _validate_staff_levels(shift_type: ShiftType) -> None:
    if not (
        shift_type.default_min_staff
        <= shift_type.default_required_staff
        <= shift_type.default_max_staff
    ):
        raise ShiftTypeError("shift_type.invalid_staff_levels")


class ShiftTypeService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = ShiftTypeRepository(db)

    async def list_all(self, *, active_only: bool = False) -> list[ShiftType]:
        return await self._repo.list_all(active_only=active_only)

    async def create(self, payload: ShiftTypeCreate) -> ShiftType:
        if await self._repo.get_by_code(payload.code) is not None:
            raise ShiftTypeError("shift_type.code_already_exists")

        shift_type = ShiftType(**payload.model_dump())
        _validate_staff_levels(shift_type)
        await self._repo.create(shift_type)
        await self._db.commit()
        await self._db.refresh(shift_type)
        return shift_type

    async def update(self, shift_type_id: uuid.UUID, payload: ShiftTypeUpdate) -> ShiftType:
        shift_type = await self._repo.get_by_id(shift_type_id)
        if shift_type is None:
            raise ShiftTypeError("shift_type.not_found")

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(shift_type, field, value)
        if shift_type.end_time <= shift_type.start_time:
            raise ShiftTypeError("shift_type.invalid_time_range")
        _validate_staff_levels(shift_type)

        await self._repo.save(shift_type)
        await self._db.commit()
        await self._db.refresh(shift_type)
        return shift_type

    # --- per-weekday overrides ------------------------------------------

    async def to_read(self, shift_type: ShiftType) -> ShiftTypeRead:
        overrides = await self._repo.list_overrides(shift_type.id)
        return ShiftTypeRead(
            id=shift_type.id,
            code=shift_type.code,
            name_pl=shift_type.name_pl,
            name_en=shift_type.name_en,
            start_time=shift_type.start_time,
            end_time=shift_type.end_time,
            color_hex=shift_type.color_hex,
            active_weekdays=shift_type.active_weekdays,
            default_required_staff=shift_type.default_required_staff,
            default_min_staff=shift_type.default_min_staff,
            default_max_staff=shift_type.default_max_staff,
            sort_order=shift_type.sort_order,
            is_active=shift_type.is_active,
            overrides=[ShiftTypeWeekdayOverrideRead.model_validate(o) for o in overrides],
        )

    async def list_all_read(self, *, active_only: bool = False) -> list[ShiftTypeRead]:
        return [await self.to_read(st) for st in await self.list_all(active_only=active_only)]

    async def upsert_override(
        self, shift_type_id: uuid.UUID, weekday: Weekday, payload: ShiftTypeWeekdayOverrideWrite
    ) -> ShiftTypeWeekdayOverrideRead:
        shift_type = await self._repo.get_by_id(shift_type_id)
        if shift_type is None:
            raise ShiftTypeError("shift_type.not_found")

        override = await self._repo.get_override(shift_type_id, weekday)
        if override is None:
            override = ShiftTypeWeekdayOverride(shift_type_id=shift_type_id, weekday=weekday)
        override.start_time = payload.start_time
        override.end_time = payload.end_time
        override.min_staff = payload.min_staff
        override.required_staff = payload.required_staff
        override.max_staff = payload.max_staff

        await self._repo.save_override(override)
        await self._db.commit()
        await self._db.refresh(override)
        return ShiftTypeWeekdayOverrideRead.model_validate(override)

    async def delete_override(self, shift_type_id: uuid.UUID, weekday: Weekday) -> None:
        override = await self._repo.get_override(shift_type_id, weekday)
        if override is None:
            raise ShiftTypeError("shift_type.override_not_found")
        await self._repo.delete_override(override)
        await self._db.commit()
