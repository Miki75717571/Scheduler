from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_invitation_token, hash_invitation_token, hash_password
from app.models.invitation import Invitation
from app.models.user import Role, User
from app.repositories.invitation_repository import InvitationRepository
from app.repositories.user_repository import UserRepository
from app.services.email_service import EmailService


class InvitationError(Exception):
    def __init__(self, message_key: str) -> None:
        self.message_key = message_key
        super().__init__(message_key)


class InvitationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._invitations = InvitationRepository(db)
        self._users = UserRepository(db)
        self._email = EmailService()

    async def create_invitation(self, *, email: str, role: Role, created_by: User) -> Invitation:
        if await self._users.get_by_email(email) is not None:
            raise InvitationError("invitation.email_already_registered")

        raw_token, token_hash = generate_invitation_token()
        invitation = Invitation(
            email=email,
            role=role,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(hours=settings.invitation_token_expire_hours),
            created_by_user_id=created_by.id,
        )
        await self._invitations.create(invitation)
        await self._db.commit()
        await self._db.refresh(invitation)

        accept_url = f"{settings.frontend_base_url}/accept-invitation?token={raw_token}"
        self._email.send_invitation_email(to=email, accept_url=accept_url)
        return invitation

    async def preview(self, raw_token: str) -> Invitation:
        return await self._get_valid_invitation(raw_token)

    async def accept(self, *, raw_token: str, full_name: str, password: str) -> User:
        invitation = await self._get_valid_invitation(raw_token)

        user = User(
            email=invitation.email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=invitation.role,
            is_active=True,
            invited_at=invitation.created_at,
            activated_at=datetime.now(UTC),
        )
        await self._users.create(user)
        invitation.accepted_at = datetime.now(UTC)
        await self._db.commit()
        await self._db.refresh(user)
        return user

    async def _get_valid_invitation(self, raw_token: str) -> Invitation:
        token_hash = hash_invitation_token(raw_token)
        invitation = await self._invitations.get_by_token_hash(token_hash)
        if invitation is None:
            raise InvitationError("invitation.not_found")
        if invitation.accepted_at is not None:
            raise InvitationError("invitation.already_used")
        if invitation.expires_at < datetime.now(UTC):
            raise InvitationError("invitation.expired")
        return invitation
