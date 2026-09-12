import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_role
from app.db.session import get_db
from app.models.assignment import Assignment
from app.models.schedule_period import SchedulePeriod
from app.models.user import Role
from app.repositories.user_repository import UserRepository
from app.rules.types import ScheduleViolation
from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentLockUpdate,
    AssignmentMove,
    AssignmentMutationResult,
    AssignmentRead,
    AuditLogRead,
    AvailableEmployeeRead,
    BulkAssignmentRequest,
    BulkAssignmentResult,
    ScheduleViolationRead,
)
from app.services.period_service import PeriodError, PeriodService
from app.services.schedule_service import AssignmentError, ScheduleService

router = APIRouter(prefix="/periods/{period_id}", tags=["assignments"])

_NOT_FOUND_KEYS = {"assignment.not_found", "assignment.slot_not_found", "assignment.user_not_found"}
_CONFLICT_KEYS = {"assignment.already_exists"}
_FORBIDDEN_KEYS = {"assignment.period_not_published"}


def _period_http_error(exc: PeriodError) -> HTTPException:
    status_code = status.HTTP_404_NOT_FOUND if exc.message_key.endswith(".not_found") else 409
    return HTTPException(status_code, detail={"message_key": exc.message_key, "params": exc.params})


def _assignment_http_error(exc: AssignmentError) -> HTTPException:
    if exc.message_key in _NOT_FOUND_KEYS:
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.message_key in _CONFLICT_KEYS:
        status_code = status.HTTP_409_CONFLICT
    elif exc.message_key in _FORBIDDEN_KEYS:
        status_code = status.HTTP_403_FORBIDDEN
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code, detail={"message_key": exc.message_key, "params": exc.params})


async def _name_by_id(db: AsyncSession, assignments: list[Assignment]) -> dict[uuid.UUID, str]:
    # Scoped to just the users appearing in these assignments - list_by_ids
    # never exposes the full roster, so this stays safe to build even for an
    # employee's own (shared-shift-filtered) assignment list.
    user_ids = {a.user_id for a in assignments}
    users = await UserRepository(db).list_by_ids(user_ids)
    return {u.id: u.full_name for u in users}


def _to_assignment_read(a: Assignment, name_by_id: dict[uuid.UUID, str]) -> AssignmentRead:
    return AssignmentRead(
        id=a.id,
        shift_slot_id=a.shift_slot_id,
        user_id=a.user_id,
        full_name=name_by_id.get(a.user_id, ""),
        source=a.source,
        is_locked=a.is_locked,
        modified_after_publish=a.modified_after_publish,
        created_by_user_id=a.created_by_user_id,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


def _to_violation_read(v: ScheduleViolation) -> ScheduleViolationRead:
    return ScheduleViolationRead(
        severity=v.severity,
        rule_code=v.rule_code,
        rule_type=v.rule_type,
        message_key=v.message_key,
        message_params=v.message_params,
        shift_slot_id=v.shift_slot_id,
        user_id=v.user_id,
    )


async def _get_period(db: AsyncSession, period_id: uuid.UUID) -> SchedulePeriod:
    try:
        return await PeriodService(db).get(period_id)
    except PeriodError as exc:
        raise _period_http_error(exc) from exc


@router.get("/assignments", response_model=list[AssignmentRead])
async def list_assignments(
    period_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID | None = Query(default=None),
) -> list[AssignmentRead]:
    period = await _get_period(db, period_id)
    try:
        assignments = await ScheduleService(db).list_visible_assignments(
            period, current_user, filter_user_id=user_id
        )
    except AssignmentError as exc:
        raise _assignment_http_error(exc) from exc
    name_by_id = await _name_by_id(db, assignments)
    return [_to_assignment_read(a, name_by_id) for a in assignments]


@router.post(
    "/assignments",
    response_model=AssignmentMutationResult,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def create_assignment(
    period_id: uuid.UUID,
    payload: AssignmentCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> AssignmentMutationResult:
    period = await _get_period(db, period_id)
    service = ScheduleService(db)
    try:
        assignment = await service.create_assignment(period, payload, actor=current_user)
    except AssignmentError as exc:
        raise _assignment_http_error(exc) from exc
    violations = await service.compute_violations(period)
    name_by_id = await _name_by_id(db, [assignment])
    return AssignmentMutationResult(
        assignment=_to_assignment_read(assignment, name_by_id),
        violations=[_to_violation_read(v) for v in violations],
    )


@router.delete(
    "/assignments/{assignment_id}",
    response_model=AssignmentMutationResult,
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def remove_assignment(
    period_id: uuid.UUID,
    assignment_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> AssignmentMutationResult:
    period = await _get_period(db, period_id)
    service = ScheduleService(db)
    try:
        await service.remove_assignment(period, assignment_id, actor=current_user)
    except AssignmentError as exc:
        raise _assignment_http_error(exc) from exc
    violations = await service.compute_violations(period)
    return AssignmentMutationResult(
        assignment=None, violations=[_to_violation_read(v) for v in violations]
    )


@router.patch(
    "/assignments/{assignment_id}/move",
    response_model=AssignmentMutationResult,
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def move_assignment(
    period_id: uuid.UUID,
    assignment_id: uuid.UUID,
    payload: AssignmentMove,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> AssignmentMutationResult:
    period = await _get_period(db, period_id)
    service = ScheduleService(db)
    try:
        assignment = await service.move_assignment(
            period, assignment_id, payload.shift_slot_id, actor=current_user
        )
    except AssignmentError as exc:
        raise _assignment_http_error(exc) from exc
    violations = await service.compute_violations(period)
    name_by_id = await _name_by_id(db, [assignment])
    return AssignmentMutationResult(
        assignment=_to_assignment_read(assignment, name_by_id),
        violations=[_to_violation_read(v) for v in violations],
    )


@router.patch(
    "/assignments/{assignment_id}/lock",
    response_model=AssignmentRead,
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def set_assignment_lock(
    period_id: uuid.UUID,
    assignment_id: uuid.UUID,
    payload: AssignmentLockUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> AssignmentRead:
    period = await _get_period(db, period_id)
    service = ScheduleService(db)
    try:
        assignment = await service.set_lock(
            period, assignment_id, payload.is_locked, actor=current_user
        )
    except AssignmentError as exc:
        raise _assignment_http_error(exc) from exc
    name_by_id = await _name_by_id(db, [assignment])
    return _to_assignment_read(assignment, name_by_id)


@router.post(
    "/assignments/bulk",
    response_model=BulkAssignmentResult,
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def bulk_assignments(
    period_id: uuid.UUID,
    payload: BulkAssignmentRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> BulkAssignmentResult:
    period = await _get_period(db, period_id)
    service = ScheduleService(db)
    try:
        assignments = await service.bulk(period, payload.operations, actor=current_user)
    except AssignmentError as exc:
        raise _assignment_http_error(exc) from exc
    violations = await service.compute_violations(period)
    name_by_id = await _name_by_id(db, assignments)
    return BulkAssignmentResult(
        assignments=[_to_assignment_read(a, name_by_id) for a in assignments],
        violations=[_to_violation_read(v) for v in violations],
    )


@router.get(
    "/violations",
    response_model=list[ScheduleViolationRead],
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def list_violations(
    period_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[ScheduleViolationRead]:
    period = await _get_period(db, period_id)
    violations = await ScheduleService(db).compute_violations(period)
    return [_to_violation_read(v) for v in violations]


@router.get(
    "/slots/{slot_id}/available-employees",
    response_model=list[AvailableEmployeeRead],
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def available_employees(
    period_id: uuid.UUID, slot_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[AvailableEmployeeRead]:
    period = await _get_period(db, period_id)
    try:
        candidates = await ScheduleService(db).available_employees(period, slot_id)
    except AssignmentError as exc:
        raise _assignment_http_error(exc) from exc
    return [
        AvailableEmployeeRead(user_id=user.id, full_name=user.full_name, status=avail_status)
        for user, avail_status in candidates
    ]


@router.get(
    "/audit-log",
    response_model=list[AuditLogRead],
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def audit_log(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    since_publish_only: bool = Query(default=False),
) -> list[AuditLogRead]:
    period = await _get_period(db, period_id)
    entries = await ScheduleService(db).list_audit_log(
        period, since_publish_only=since_publish_only
    )
    return [AuditLogRead.model_validate(e) for e in entries]
