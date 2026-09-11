import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_role
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import Role
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserAdminUpdate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def get_me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.patch("/me", response_model=UserRead)
async def update_me(
    payload: UserUpdate, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> UserRead:
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.phone is not None:
        current_user.phone = payload.phone
    if payload.locale is not None:
        current_user.locale = payload.locale
    if payload.password is not None:
        current_user.password_hash = hash_password(payload.password)

    await UserRepository(db).save(current_user)
    await db.commit()
    await db.refresh(current_user)
    return UserRead.model_validate(current_user)


@router.get("", response_model=list[UserRead], dependencies=[Depends(require_role(Role.ADMIN))])
async def list_users(db: AsyncSession = Depends(get_db)) -> list[UserRead]:
    return [UserRead.model_validate(u) for u in await UserRepository(db).list_all()]


@router.patch(
    "/{user_id}", response_model=UserRead, dependencies=[Depends(require_role(Role.ADMIN))]
)
async def admin_update_user(
    user_id: uuid.UUID, payload: UserAdminUpdate, db: AsyncSession = Depends(get_db)
) -> UserRead:
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"message_key": "user.not_found"})

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    await repo.save(user)
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.post(
    "/{user_id}/deactivate",
    response_model=UserRead,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def deactivate_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> UserRead:
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"message_key": "user.not_found"})

    user.is_active = False
    await repo.save(user)
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)
