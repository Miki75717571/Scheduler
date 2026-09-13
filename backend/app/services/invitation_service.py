import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_invitation_token, hash_invitation_token, hash_password
from app.models.invitation import Invitation
from app.models.user import Role, User
from app.repositories.invitation_repository import InvitationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.invitation import InvitationRead, InvitationStatus
from app.services.email_service import EmailService


class InvitationError(Exception):
    def __init__(self, message_key: str) -> None:
        self.message_key = message_key
        super().__init__(message_key)


def _status(invitation: Invitation) -> InvitationStatus:
    if invitation.accepted_at is not None:
        return "ACCEPTED"
    if invitation.revoked_at is not None:
        return "REVOKED"
    if invitation.expires_at < datetime.now(UTC):
        return "EXPIRED"
    return "PENDING"


def _reveals_accept_url() -> bool:
    """The link is only useful to hand to the admin when the configured
    email provider can't actually deliver the invite itself - see CLAUDE.md
    JOB 8: staying on the console provider is a deliberate, ongoing choice
    here, not just a dev-mode convenience, so this is NOT gated on
    app_env.
    """
    return settings.email_provider != "resend"


class InvitationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._invitations = InvitationRepository(db)
        self._users = UserRepository(db)
        self._email = EmailService()

    async def create_invitation(
        self, *, email: str, role: Role, created_by: User
    ) -> tuple[Invitation, str]:
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
        return invitation, accept_url

    async def list_all(self) -> list[Invitation]:
        return await self._invitations.list_all()

    async def resend(self, invitation_id: uuid.UUID) -> tuple[Invitation, str]:
        """Issues a fresh token and expiry on the same row - the old link
        stops working immediately (its hash no longer matches anything
        stored). Refused once accepted; a revoked invitation can still be
        resent, which implicitly un-revokes it - resending is itself an
        explicit decision to invite this person again.
        """
        invitation = await self._invitations.get_by_id(invitation_id)
        if invitation is None:
            raise InvitationError("invitation.not_found")
        if invitation.accepted_at is not None:
            raise InvitationError("invitation.already_used")

        raw_token, token_hash = generate_invitation_token()
        invitation.token_hash = token_hash
        invitation.expires_at = datetime.now(UTC) + timedelta(
            hours=settings.invitation_token_expire_hours
        )
        invitation.revoked_at = None
        await self._invitations.save(invitation)
        await self._db.commit()
        await self._db.refresh(invitation)

        accept_url = f"{settings.frontend_base_url}/accept-invitation?token={raw_token}"
        self._email.send_invitation_email(to=invitation.email, accept_url=accept_url)
        return invitation, accept_url

    async def revoke(self, invitation_id: uuid.UUID) -> Invitation:
        invitation = await self._invitations.get_by_id(invitation_id)
        if invitation is None:
            raise InvitationError("invitation.not_found")
        if invitation.accepted_at is not None:
            raise InvitationError("invitation.already_used")

        invitation.revoked_at = datetime.now(UTC)
        await self._invitations.save(invitation)
        await self._db.commit()
        await self._db.refresh(invitation)
        return invitation

    def to_read(self, invitation: Invitation, *, accept_url: str | None = None) -> InvitationRead:
        return InvitationRead(
            id=invitation.id,
            email=invitation.email,
            role=invitation.role,
            expires_at=invitation.expires_at,
            accepted_at=invitation.accepted_at,
            revoked_at=invitation.revoked_at,
            status=_status(invitation),
            accept_url=accept_url if _reveals_accept_url() else None,
        )

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
        if invitation.revoked_at is not None:
            raise InvitationError("invitation.revoked")
        if invitation.expires_at < datetime.now(UTC):
            raise InvitationError("invitation.expired")
        return invitation
