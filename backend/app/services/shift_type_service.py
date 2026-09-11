import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shift_type import ShiftType
from app.repositories.shift_type_repository import ShiftTypeRepository
from app.schemas.shift_type import ShiftTypeCreate, ShiftTypeUpdate


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
