import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_role
from app.db.session import get_db
from app.models.schedule_period import PeriodState
from app.models.user import Role
from app.schemas.period import PeriodCreate, PeriodRead, PeriodStateUpdate
from app.schemas.shift_slot import ShiftSlotRead, ShiftSlotUpdate
from app.services.period_service import PeriodError, PeriodService
from app.services.schedule_service import ScheduleService

router = APIRouter(prefix="/periods", tags=["periods"])

_NOT_FOUND_SUFFIXES = (".not_found",)
_CONFLICT_KEYS = {
    "period.already_exists",
    "period.illegal_transition",
    "period.publish_blocked_by_errors",
}


def _http_error(exc: PeriodError) -> HTTPException:
    if exc.message_key.endswith(_NOT_FOUND_SUFFIXES):
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.message_key in _CONFLICT_KEYS:
        status_code = status.HTTP_409_CONFLICT
    else:
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(status_code, detail={"message_key": exc.message_key, "params": exc.params})


@router.get("", response_model=list[PeriodRead])
async def list_periods(
    current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> list[PeriodRead]:
    return [PeriodRead.model_validate(p) for p in await PeriodService(db).list_all()]


@router.post(
    "",
    response_model=PeriodRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def create_period(payload: PeriodCreate, db: AsyncSession = Depends(get_db)) -> PeriodRead:
    try:
        period = await PeriodService(db).create(payload)
    except PeriodError as exc:
        raise _http_error(exc) from exc
    return PeriodRead.model_validate(period)


@router.get("/{period_id}", response_model=PeriodRead)
async def get_period(
    period_id: uuid.UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> PeriodRead:
    try:
        period = await PeriodService(db).get(period_id)
    except PeriodError as exc:
        raise _http_error(exc) from exc
    return PeriodRead.model_validate(period)


@router.patch(
    "/{period_id}/state",
    response_model=PeriodRead,
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def update_period_state(
    period_id: uuid.UUID,
    payload: PeriodStateUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> PeriodRead:
    service = PeriodService(db)
    try:
        period = await service.get(period_id)

        override_used = False
        if payload.state == PeriodState.PUBLISHED and period.state == PeriodState.GENERATED:
            violations = await ScheduleService(db).compute_violations(period)
            error_count = sum(1 for v in violations if v.severity == "ERROR")
            if error_count and not payload.override_violations:
                raise PeriodError("period.publish_blocked_by_errors", {"error_count": error_count})
            override_used = error_count > 0 and payload.override_violations

        period = await service.transition_state(
            period, payload.state, actor=current_user, override_used=override_used
        )
    except PeriodError as exc:
        raise _http_error(exc) from exc
    return PeriodRead.model_validate(period)


@router.get("/{period_id}/slots", response_model=list[ShiftSlotRead])
async def list_slots(
    period_id: uuid.UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> list[ShiftSlotRead]:
    service = PeriodService(db)
    try:
        await service.get(period_id)
    except PeriodError as exc:
        raise _http_error(exc) from exc
    return [ShiftSlotRead.model_validate(s) for s in await service.list_slots(period_id)]


@router.patch(
    "/{period_id}/slots/{slot_id}",
    response_model=ShiftSlotRead,
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def update_slot(
    period_id: uuid.UUID,
    slot_id: uuid.UUID,
    payload: ShiftSlotUpdate,
    db: AsyncSession = Depends(get_db),
) -> ShiftSlotRead:
    service = PeriodService(db)
    try:
        period = await service.get(period_id)
        slot = await service.update_slot(period, slot_id, payload)
    except PeriodError as exc:
        raise _http_error(exc) from exc
    return ShiftSlotRead.model_validate(slot)
