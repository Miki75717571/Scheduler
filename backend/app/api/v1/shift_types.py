import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_role
from app.db.session import get_db
from app.models.user import Role
from app.schemas.shift_type import ShiftTypeCreate, ShiftTypeRead, ShiftTypeUpdate
from app.services.shift_type_service import ShiftTypeError, ShiftTypeService

router = APIRouter(prefix="/shift-types", tags=["shift-types"])

_NOT_FOUND_KEYS = {"shift_type.not_found"}


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
    shift_types = await ShiftTypeService(db).list_all()
    return [ShiftTypeRead.model_validate(s) for s in shift_types]


@router.post(
    "",
    response_model=ShiftTypeRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def create_shift_type(
    payload: ShiftTypeCreate, db: AsyncSession = Depends(get_db)
) -> ShiftTypeRead:
    try:
        shift_type = await ShiftTypeService(db).create(payload)
    except ShiftTypeError as exc:
        raise _http_error(exc) from exc
    return ShiftTypeRead.model_validate(shift_type)


@router.patch(
    "/{shift_type_id}",
    response_model=ShiftTypeRead,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def update_shift_type(
    shift_type_id: uuid.UUID, payload: ShiftTypeUpdate, db: AsyncSession = Depends(get_db)
) -> ShiftTypeRead:
    try:
        shift_type = await ShiftTypeService(db).update(shift_type_id, payload)
    except ShiftTypeError as exc:
        raise _http_error(exc) from exc
    return ShiftTypeRead.model_validate(shift_type)
