import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_role
from app.db.session import get_db
from app.models.availability import Availability, AvailabilitySubmission, SubmissionStatus
from app.models.user import Role, User
from app.repositories.user_repository import UserRepository
from app.rules.types import RuleCheckResult
from app.schemas.availability import (
    AvailabilityDetailRead,
    AvailabilityEntryRead,
    AvailabilitySubmissionRead,
    AvailabilityWriteRequest,
    RuleCheckResultRead,
    SubmissionTrackerEntry,
)
from app.services.availability_service import AvailabilityError, AvailabilityService
from app.services.period_service import PeriodError, PeriodService

router = APIRouter(prefix="/periods/{period_id}/availability", tags=["availability"])


def _forbidden() -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, detail={"message_key": "auth.forbidden"})


def _period_not_found(exc: PeriodError) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail={"message_key": exc.message_key})


def _availability_http_error(exc: AvailabilityError) -> HTTPException:
    if exc.message_key == "availability.hard_rules_failed":
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    elif exc.message_key == "availability.invalid_shift_slot":
        status_code = status.HTTP_400_BAD_REQUEST
    else:
        status_code = status.HTTP_409_CONFLICT
    return HTTPException(status_code, detail={"message_key": exc.message_key, "params": exc.params})


def _ensure_self_or_manager(current_user: User, target_user_id: uuid.UUID) -> None:
    if current_user.id == target_user_id:
        return
    if current_user.role in (Role.MANAGER, Role.ADMIN):
        return
    raise _forbidden()


def _to_rule_result_read(result: RuleCheckResult) -> RuleCheckResultRead:
    return RuleCheckResultRead(
        rule_code=result.rule_code,
        severity=result.severity,
        passed=result.passed,
        message_key=result.message_key,
        message_params=result.message_params,
    )


def _to_detail(
    submission: AvailabilitySubmission,
    entries: list[Availability],
    validation: list[RuleCheckResult],
) -> AvailabilityDetailRead:
    return AvailabilityDetailRead(
        submission=AvailabilitySubmissionRead.model_validate(submission),
        entries=[
            AvailabilityEntryRead(shift_slot_id=e.shift_slot_id, status=e.status, note=e.note)
            for e in entries
        ],
        validation=[_to_rule_result_read(r) for r in validation],
    )


async def _resolve_target_user(db: AsyncSession, current_user: User, user_id: uuid.UUID) -> User:
    if current_user.id == user_id:
        return current_user
    target_user = await UserRepository(db).get_by_id(user_id)
    if target_user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"message_key": "user.not_found"})
    return target_user


@router.get(
    "/tracker",
    response_model=list[SubmissionTrackerEntry],
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def submission_tracker(
    period_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[SubmissionTrackerEntry]:
    try:
        period = await PeriodService(db).get(period_id)
    except PeriodError as exc:
        raise _period_not_found(exc) from exc

    users = [u for u in await UserRepository(db).list_all() if u.is_active]
    pairs = await AvailabilityService(db).list_submission_tracker(period=period, users=users)
    return [
        SubmissionTrackerEntry(
            user_id=u.id,
            full_name=u.full_name,
            employment_type=u.employment_type.value if u.employment_type else None,
            status=s.status if s is not None else SubmissionStatus.NOT_STARTED,
            submitted_at=s.submitted_at if s is not None else None,
            reopened_by_manager=s.reopened_by_manager if s is not None else False,
        )
        for u, s in pairs
    ]


@router.get("/{user_id}", response_model=AvailabilityDetailRead)
async def get_availability(
    period_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> AvailabilityDetailRead:
    _ensure_self_or_manager(current_user, user_id)
    try:
        period = await PeriodService(db).get(period_id)
    except PeriodError as exc:
        raise _period_not_found(exc) from exc

    target_user = await _resolve_target_user(db, current_user, user_id)
    submission, entries, validation = await AvailabilityService(db).get_detail(
        user=target_user, period=period
    )
    return _to_detail(submission, entries, validation)


@router.put("/{user_id}", response_model=AvailabilityDetailRead)
async def write_availability(
    period_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: AvailabilityWriteRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> AvailabilityDetailRead:
    if current_user.id != user_id:
        raise _forbidden()
    try:
        period = await PeriodService(db).get(period_id)
    except PeriodError as exc:
        raise _period_not_found(exc) from exc

    service = AvailabilityService(db)
    try:
        await service.write(user=current_user, period=period, entries=payload.entries)
    except AvailabilityError as exc:
        raise _availability_http_error(exc) from exc
    submission, entries, validation = await service.get_detail(user=current_user, period=period)
    return _to_detail(submission, entries, validation)


@router.get("/{user_id}/validate", response_model=list[RuleCheckResultRead])
async def validate_availability(
    period_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[RuleCheckResultRead]:
    _ensure_self_or_manager(current_user, user_id)
    try:
        period = await PeriodService(db).get(period_id)
    except PeriodError as exc:
        raise _period_not_found(exc) from exc

    target_user = await _resolve_target_user(db, current_user, user_id)
    _, _, validation = await AvailabilityService(db).get_detail(user=target_user, period=period)
    return [_to_rule_result_read(r) for r in validation]


@router.post("/{user_id}/submit", response_model=AvailabilityDetailRead)
async def submit_availability(
    period_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> AvailabilityDetailRead:
    if current_user.id != user_id:
        raise _forbidden()
    try:
        period = await PeriodService(db).get(period_id)
    except PeriodError as exc:
        raise _period_not_found(exc) from exc

    service = AvailabilityService(db)
    try:
        await service.submit(user=current_user, period=period)
    except AvailabilityError as exc:
        raise _availability_http_error(exc) from exc
    submission, entries, validation = await service.get_detail(user=current_user, period=period)
    return _to_detail(submission, entries, validation)


@router.post(
    "/{user_id}/reopen",
    response_model=AvailabilitySubmissionRead,
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def reopen_availability(
    period_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> AvailabilitySubmissionRead:
    try:
        period = await PeriodService(db).get(period_id)
    except PeriodError as exc:
        raise _period_not_found(exc) from exc
    try:
        submission = await AvailabilityService(db).reopen(
            period=period, user_id=user_id, reopened=True
        )
    except AvailabilityError as exc:
        raise _availability_http_error(exc) from exc
    return AvailabilitySubmissionRead.model_validate(submission)


@router.delete(
    "/{user_id}/reopen",
    response_model=AvailabilitySubmissionRead,
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def revoke_reopen_availability(
    period_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> AvailabilitySubmissionRead:
    try:
        period = await PeriodService(db).get(period_id)
    except PeriodError as exc:
        raise _period_not_found(exc) from exc
    try:
        submission = await AvailabilityService(db).reopen(
            period=period, user_id=user_id, reopened=False
        )
    except AvailabilityError as exc:
        raise _availability_http_error(exc) from exc
    return AvailabilitySubmissionRead.model_validate(submission)
