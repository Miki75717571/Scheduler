import uuid

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

_NOT_FOUND_KEYS = {"invitation.not_found"}


def _http_error(exc: InvitationError) -> HTTPException:
    if exc.message_key in _NOT_FOUND_KEYS:
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.message_key == "invitation.already_used":
        status_code = status.HTTP_409_CONFLICT
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code, detail={"message_key": exc.message_key})


@router.get(
    "", response_model=list[InvitationRead], dependencies=[Depends(require_role(Role.ADMIN))]
)
async def list_invitations(db: AsyncSession = Depends(get_db)) -> list[InvitationRead]:
    service = InvitationService(db)
    return [service.to_read(i) for i in await service.list_all()]


@router.post(
    "",
    response_model=InvitationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def create_invitation(
    payload: InvitationCreate, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> InvitationRead:
    service = InvitationService(db)
    try:
        invitation, accept_url = await service.create_invitation(
            email=payload.email, role=payload.role, created_by=current_user
        )
    except InvitationError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail={"message_key": exc.message_key}
        ) from exc
    return service.to_read(invitation, accept_url=accept_url)


@router.post(
    "/{invitation_id}/resend",
    response_model=InvitationRead,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def resend_invitation(
    invitation_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> InvitationRead:
    service = InvitationService(db)
    try:
        invitation, accept_url = await service.resend(invitation_id)
    except InvitationError as exc:
        raise _http_error(exc) from exc
    return service.to_read(invitation, accept_url=accept_url)


@router.post(
    "/{invitation_id}/revoke",
    response_model=InvitationRead,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def revoke_invitation(
    invitation_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> InvitationRead:
    service = InvitationService(db)
    try:
        invitation = await service.revoke(invitation_id)
    except InvitationError as exc:
        raise _http_error(exc) from exc
    return service.to_read(invitation)


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
