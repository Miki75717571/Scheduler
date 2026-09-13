import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_role
from app.db.session import get_db
from app.models.user import Role
from app.rules.weekdays import Weekday
from app.schemas.shift_type import (
    ShiftTypeCreate,
    ShiftTypeRead,
    ShiftTypeUpdate,
    ShiftTypeWeekdayOverrideRead,
    ShiftTypeWeekdayOverrideWrite,
)
from app.services.shift_type_service import ShiftTypeError, ShiftTypeService

router = APIRouter(prefix="/shift-types", tags=["shift-types"])

_NOT_FOUND_KEYS = {"shift_type.not_found", "shift_type.override_not_found"}


def _http_error(exc: ShiftTypeError) -> HTTPException:
    if exc.message_key in _NOT_FOUND_KEYS:
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.message_key == "shift_type.code_already_exists":
        status_code = status.HTTP_409_CONFLICT
    else:
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(status_code, detail={"message_key": exc.message_key})


@router.get("", response_model=list[ShiftTypeRead])
async def list_shift_types(
    current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> list[ShiftTypeRead]:
    return await ShiftTypeService(db).list_all_read()


@router.post(
    "",
    response_model=ShiftTypeRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def create_shift_type(
    payload: ShiftTypeCreate, db: AsyncSession = Depends(get_db)
) -> ShiftTypeRead:
    service = ShiftTypeService(db)
    try:
        shift_type = await service.create(payload)
    except ShiftTypeError as exc:
        raise _http_error(exc) from exc
    return await service.to_read(shift_type)


@router.patch(
    "/{shift_type_id}",
    response_model=ShiftTypeRead,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def update_shift_type(
    shift_type_id: uuid.UUID, payload: ShiftTypeUpdate, db: AsyncSession = Depends(get_db)
) -> ShiftTypeRead:
    service = ShiftTypeService(db)
    try:
        shift_type = await service.update(shift_type_id, payload)
    except ShiftTypeError as exc:
        raise _http_error(exc) from exc
    return await service.to_read(shift_type)


@router.put(
    "/{shift_type_id}/overrides/{weekday}",
    response_model=ShiftTypeWeekdayOverrideRead,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def upsert_shift_type_override(
    shift_type_id: uuid.UUID,
    weekday: Weekday,
    payload: ShiftTypeWeekdayOverrideWrite,
    db: AsyncSession = Depends(get_db),
) -> ShiftTypeWeekdayOverrideRead:
    try:
        return await ShiftTypeService(db).upsert_override(shift_type_id, weekday, payload)
    except ShiftTypeError as exc:
        raise _http_error(exc) from exc


@router.delete(
    "/{shift_type_id}/overrides/{weekday}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def delete_shift_type_override(
    shift_type_id: uuid.UUID, weekday: Weekday, db: AsyncSession = Depends(get_db)
) -> None:
    try:
        await ShiftTypeService(db).delete_override(shift_type_id, weekday)
    except ShiftTypeError as exc:
        raise _http_error(exc) from exc
