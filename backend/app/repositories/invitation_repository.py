import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invitation import Invitation


class InvitationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, invitation_id: uuid.UUID) -> Invitation | None:
        return await self._db.get(Invitation, invitation_id)

    async def create(self, invitation: Invitation) -> Invitation:
        self._db.add(invitation)
        await self._db.flush()
        return invitation

    async def save(self, invitation: Invitation) -> Invitation:
        await self._db.flush()
        return invitation

    async def get_by_token_hash(self, token_hash: str) -> Invitation | None:
        result = await self._db.execute(
            select(Invitation).where(Invitation.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def list_pending(self) -> list[Invitation]:
        result = await self._db.execute(
            select(Invitation)
            .where(Invitation.accepted_at.is_(None))
            .order_by(Invitation.created_at.desc())
        )
        return list(result.scalars())

    async def list_all(self) -> list[Invitation]:
        result = await self._db.execute(select(Invitation).order_by(Invitation.created_at.desc()))
        return list(result.scalars())
