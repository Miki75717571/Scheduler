from dataclasses import dataclass

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository


class AuthError(Exception):
    def __init__(self, message_key: str) -> None:
        self.message_key = message_key
        super().__init__(message_key)


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    user: User


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self._users = UserRepository(db)

    async def login(self, *, email: str, password: str) -> TokenPair:
        user = await self._users.get_by_email(email)
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            raise AuthError("auth.invalid_credentials")
        return self._issue_tokens(user)

    async def refresh(self, *, refresh_token: str) -> TokenPair:
        try:
            payload = decode_refresh_token(refresh_token)
        except jwt.PyJWTError as exc:
            raise AuthError("auth.invalid_token") from exc

        user = await self._users.get_by_id(payload["sub"])
        if user is None or not user.is_active:
            raise AuthError("auth.invalid_token")
        return self._issue_tokens(user)

    def _issue_tokens(self, user: User) -> TokenPair:
        return TokenPair(
            access_token=create_access_token(str(user.id), user.role.value),
            refresh_token=create_refresh_token(str(user.id)),
            user=user,
        )
