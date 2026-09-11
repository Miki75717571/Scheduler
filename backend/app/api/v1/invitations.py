from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_role
from app.db.session import get_db
from app.models.user import Role
from app.schemas.invitation import (
    InvitationAccept,
    InvitationCreate,
    InvitationPreview,
    InvitationRead,
)
from app.schemas.user import UserRead
from app.services.invitation_service import InvitationError, InvitationService

router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.post(
    "",
    response_model=InvitationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def create_invitation(
    payload: InvitationCreate, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> InvitationRead:
    try:
        invitation = await InvitationService(db).create_invitation(
            email=payload.email, role=payload.role, created_by=current_user
        )
    except InvitationError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail={"message_key": exc.message_key}
        ) from exc
    return InvitationRead.model_validate(invitation)


@router.get("/{token}", response_model=InvitationPreview)
async def preview_invitation(token: str, db: AsyncSession = Depends(get_db)) -> InvitationPreview:
    try:
        invitation = await InvitationService(db).preview(token)
    except InvitationError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"message_key": exc.message_key}
        ) from exc
    return InvitationPreview.model_validate(invitation)


@router.post("/accept", response_model=UserRead)
async def accept_invitation(
    payload: InvitationAccept, db: AsyncSession = Depends(get_db)
) -> UserRead:
    try:
        user = await InvitationService(db).accept(
            raw_token=payload.token, full_name=payload.full_name, password=payload.password
        )
    except InvitationError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"message_key": exc.message_key}
        ) from exc
    return UserRead.model_validate(user)
