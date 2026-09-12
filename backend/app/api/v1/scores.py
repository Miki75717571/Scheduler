import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_role
from app.db.session import get_db
from app.models.user import Role
from app.repositories.user_repository import UserRepository
from app.schemas.employee_score import (
    EmployeeScoreCreate,
    ScoreEntryRead,
    ScoreGridRow,
    ScoreHistoryEntryRead,
)
from app.schemas.score_criterion import (
    ScoreCriterionCreate,
    ScoreCriterionRead,
    ScoreCriterionUpdate,
    ScoreWeightsUpdate,
)
from app.services.score_service import ScoreError, ScoreService

router = APIRouter(tags=["scores"])

_NOT_FOUND_KEYS = {
    "score_criterion.not_found",
    "score.user_not_found",
    "score.criterion_not_found",
}
_CONFLICT_KEYS = {"score_criterion.code_already_exists"}


def _http_error(exc: ScoreError) -> HTTPException:
    if exc.message_key in _NOT_FOUND_KEYS:
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.message_key in _CONFLICT_KEYS:
        status_code = status.HTTP_409_CONFLICT
    else:
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(status_code, detail={"message_key": exc.message_key, "params": exc.params})


# --- criteria: read for manager+admin, manage for admin only -------------


@router.get(
    "/score-criteria",
    response_model=list[ScoreCriterionRead],
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def list_score_criteria(
    db: AsyncSession = Depends(get_db), active_only: bool = Query(default=False)
) -> list[ScoreCriterionRead]:
    criteria = await ScoreService(db).list_criteria(active_only=active_only)
    return [ScoreCriterionRead.model_validate(c) for c in criteria]


@router.post(
    "/score-criteria",
    response_model=ScoreCriterionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def create_score_criterion(
    payload: ScoreCriterionCreate, db: AsyncSession = Depends(get_db)
) -> ScoreCriterionRead:
    try:
        criterion = await ScoreService(db).create_criterion(payload)
    except ScoreError as exc:
        raise _http_error(exc) from exc
    return ScoreCriterionRead.model_validate(criterion)


@router.patch(
    "/score-criteria/{criterion_id}",
    response_model=ScoreCriterionRead,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def update_score_criterion(
    criterion_id: uuid.UUID, payload: ScoreCriterionUpdate, db: AsyncSession = Depends(get_db)
) -> ScoreCriterionRead:
    try:
        criterion = await ScoreService(db).update_criterion(criterion_id, payload)
    except ScoreError as exc:
        raise _http_error(exc) from exc
    return ScoreCriterionRead.model_validate(criterion)


@router.post(
    "/score-criteria/{criterion_id}/deactivate",
    response_model=ScoreCriterionRead,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def deactivate_score_criterion(
    criterion_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> ScoreCriterionRead:
    try:
        criterion = await ScoreService(db).deactivate_criterion(criterion_id)
    except ScoreError as exc:
        raise _http_error(exc) from exc
    return ScoreCriterionRead.model_validate(criterion)


@router.put(
    "/score-criteria/weights",
    response_model=list[ScoreCriterionRead],
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def update_score_criteria_weights(
    payload: ScoreWeightsUpdate, db: AsyncSession = Depends(get_db)
) -> list[ScoreCriterionRead]:
    try:
        criteria = await ScoreService(db).update_weights(payload)
    except ScoreError as exc:
        raise _http_error(exc) from exc
    return [ScoreCriterionRead.model_validate(c) for c in criteria]


# --- scores: manager+admin only, never employee-facing --------------------


@router.get(
    "/scores/grid",
    response_model=list[ScoreGridRow],
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def get_score_grid(
    db: AsyncSession = Depends(get_db), as_of: date | None = Query(default=None)
) -> list[ScoreGridRow]:
    employees = [
        u for u in await UserRepository(db).list_all() if u.role == Role.EMPLOYEE and u.is_active
    ]
    return await ScoreService(db).get_grid(employees, as_of=as_of)


@router.post(
    "/users/{user_id}/scores",
    response_model=ScoreEntryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def set_employee_score(
    user_id: uuid.UUID,
    payload: EmployeeScoreCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ScoreEntryRead:
    try:
        score = await ScoreService(db).set_score(
            user_id=user_id, payload=payload, actor=current_user
        )
    except ScoreError as exc:
        raise _http_error(exc) from exc
    return ScoreEntryRead(
        criterion_id=score.criterion_id,
        value=score.value,
        effective_from=score.effective_from,
        set_by_user_id=score.set_by_user_id,
        note=score.note,
    )


@router.get(
    "/users/{user_id}/scores/history",
    response_model=list[ScoreHistoryEntryRead],
    dependencies=[Depends(require_role(Role.MANAGER, Role.ADMIN))],
)
async def get_employee_score_history(
    user_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[ScoreHistoryEntryRead]:
    try:
        return await ScoreService(db).get_history(user_id)
    except ScoreError as exc:
        raise _http_error(exc) from exc
