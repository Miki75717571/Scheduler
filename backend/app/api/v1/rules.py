import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_role
from app.db.session import get_db
from app.models.user import Role
from app.schemas.rule import RestConflictRead, RuleCreate, RuleRead, RuleUpdate
from app.services.rule_service import RuleError, RuleService

router = APIRouter(
    prefix="/rules", tags=["rules"], dependencies=[Depends(require_role(Role.ADMIN))]
)


def _http_error(exc: RuleError) -> HTTPException:
    if exc.message_key == "rule.not_found":
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.message_key == "rule.code_already_exists":
        status_code = status.HTTP_409_CONFLICT
    else:
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(status_code, detail={"message_key": exc.message_key, "params": exc.params})


@router.get("", response_model=list[RuleRead])
async def list_rules(db: AsyncSession = Depends(get_db)) -> list[RuleRead]:
    return [RuleRead.model_validate(r) for r in await RuleService(db).list_all()]


@router.get("/rest-conflicts", response_model=list[RestConflictRead])
async def rest_conflicts(db: AsyncSession = Depends(get_db)) -> list[RestConflictRead]:
    conflicts = await RuleService(db).rest_conflicts()
    return [
        RestConflictRead(
            from_shift_type_code=c.from_shift_type_code,
            from_weekday=c.from_weekday.value,
            to_shift_type_code=c.to_shift_type_code,
            to_weekday=c.to_weekday.value,
            gap_hours=c.gap_hours,
            required_hours=c.required_hours,
        )
        for c in conflicts
    ]


@router.post("", response_model=RuleRead, status_code=status.HTTP_201_CREATED)
async def create_rule(payload: RuleCreate, db: AsyncSession = Depends(get_db)) -> RuleRead:
    try:
        rule = await RuleService(db).create(payload)
    except RuleError as exc:
        raise _http_error(exc) from exc
    return RuleRead.model_validate(rule)


@router.patch("/{rule_id}", response_model=RuleRead)
async def update_rule(
    rule_id: uuid.UUID, payload: RuleUpdate, db: AsyncSession = Depends(get_db)
) -> RuleRead:
    try:
        rule = await RuleService(db).update(rule_id, payload)
    except RuleError as exc:
        raise _http_error(exc) from exc
    return RuleRead.model_validate(rule)
