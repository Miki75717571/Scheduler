import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """All DB access for users. Callers are responsible for checking the acting
    user's role before invoking admin-only methods like `list_all` - routers
    enforce that via `require_role`, this layer enforces it by never exposing
    a "get any user by arbitrary id" path to non-admin routes.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, user_id: str | uuid.UUID) -> User | None:
        # Normalize: callers pass a raw string here (e.g. deps.py decoding a
        # JWT `sub` claim). sa.Uuid's non-native (SQLite) bind path requires an
        # actual uuid.UUID instance - Postgres's driver-level leniency about
        # accepting either had been masking this.
        if isinstance(user_id, str):
            try:
                user_id = uuid.UUID(user_id)
            except ValueError:
                return None
        return await self._db.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self._db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[User]:
        result = await self._db.execute(select(User).order_by(User.full_name))
        return list(result.scalars())

    async def create(self, user: User) -> User:
        self._db.add(user)
        await self._db.flush()
        return user

    async def save(self, user: User) -> User:
        await self._db.flush()
        return user
