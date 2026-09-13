import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_role
from app.db.session import get_db, get_session_factory
from app.models.user import Role
from app.repositories.solver_weight_config_repository import SolverWeightConfigRepository
from app.schemas.schedule_run import ScheduleRunCreate, ScheduleRunRead
from app.schemas.solver_weights import SolverWeightsRead, SolverWeightsUpdate
from app.services.period_service import PeriodError, PeriodService
from app.services.solver_service import SolverError, SolverService, run_solver_in_background

router = APIRouter(tags=["schedule-runs"])

_NOT_FOUND_SUFFIXES = (".not_found",)


def _http_error(exc: PeriodError | SolverError) -> HTTPException:
    if exc.message_key.endswith(_NOT_FOUND_SUFFIXES):
        status_code = status.HTTP_404_NOT_FOUND
    else:
        status_code = status.HTTP_409_CONFLICT
    return HTTPException(status_code, detail={"message_key": exc.message_key, "params": exc.params})


@router.post(
    "/periods/{period_id}/schedule-runs",
    response_model=ScheduleRunRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def create_schedule_run(
    period_id: uuid.UUID,
    payload: ScheduleRunCreate,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    session_factory: Callable[[], AsyncSession] = Depends(get_session_factory),
) -> ScheduleRunRead:
    """Creates the ScheduleRun row and returns immediately - the actual solve
    happens in a background task, never inside this request (CLAUDE.md
    "Running it"). Poll GET /schedule-runs/{run_id} for status.
    """
    try:
        period = await PeriodService(db).get(period_id)
        run = await SolverService(db).create_run(
            period, actor=current_user, time_limit_seconds=payload.time_limit_seconds
        )
    except (PeriodError, SolverError) as exc:
        raise _http_error(exc) from exc

    background_tasks.add_task(run_solver_in_background, run.id, session_factory)
    return ScheduleRunRead.model_validate(run)


@router.get(
    "/periods/{period_id}/schedule-runs",
    response_model=list[ScheduleRunRead],
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def list_schedule_runs(
    period_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[ScheduleRunRead]:
    try:
        period = await PeriodService(db).get(period_id)
    except PeriodError as exc:
        raise _http_error(exc) from exc
    runs = await SolverService(db).list_runs(period)
    return [ScheduleRunRead.model_validate(r) for r in runs]


@router.get(
    "/schedule-runs/{run_id}",
    response_model=ScheduleRunRead,
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def get_schedule_run(
    run_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> ScheduleRunRead:
    try:
        run = await SolverService(db).get_run(run_id)
    except SolverError as exc:
        raise _http_error(exc) from exc
    return ScheduleRunRead.model_validate(run)


@router.post(
    "/schedule-runs/{run_id}/revert",
    response_model=ScheduleRunRead,
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def revert_schedule_run(
    run_id: uuid.UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> ScheduleRunRead:
    """Restores the period's assignments to exactly what they were right
    before this run - the manager's one-click undo (CLAUDE.md "protect my
    manual work").
    """
    try:
        run = await SolverService(db).revert_run(run_id, actor=current_user)
    except SolverError as exc:
        raise _http_error(exc) from exc
    return ScheduleRunRead.model_validate(run)


@router.get(
    "/solver/weights",
    response_model=SolverWeightsRead,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def get_solver_weights(db: AsyncSession = Depends(get_db)) -> SolverWeightsRead:
    config = await SolverWeightConfigRepository(db).get_or_create_default()
    await db.commit()
    return SolverWeightsRead.model_validate(config)


@router.put(
    "/solver/weights",
    response_model=SolverWeightsRead,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def update_solver_weights(
    payload: SolverWeightsUpdate, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> SolverWeightsRead:
    repo = SolverWeightConfigRepository(db)
    config = await repo.get_or_create_default()
    for field, value in payload.model_dump().items():
        setattr(config, field, value)
    config.updated_at = datetime.now(UTC)
    config.updated_by_user_id = current_user.id
    await repo.save(config)
    await db.commit()
    await db.refresh(config)
    return SolverWeightsRead.model_validate(config)
