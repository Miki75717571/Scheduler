from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.schemas.auth import AccessTokenResponse, LoginRequest
from app.schemas.user import UserRead
from app.services.auth_service import AuthError, AuthService, TokenPair

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _token_response(tokens: TokenPair) -> AccessTokenResponse:
    return AccessTokenResponse(
        access_token=tokens.access_token, user=UserRead.model_validate(tokens.user)
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.app_env != "development",
        samesite="lax",
        max_age=settings.jwt_refresh_token_expire_days * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
    )


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> AccessTokenResponse:
    try:
        tokens = await AuthService(db).login(email=payload.email, password=payload.password)
    except AuthError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail={"message_key": exc.message_key}
        ) from exc
    _set_refresh_cookie(response, tokens.refresh_token)
    return _token_response(tokens)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
) -> AccessTokenResponse:
    if refresh_token is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail={"message_key": "auth.missing_token"}
        )
    try:
        tokens = await AuthService(db).refresh(refresh_token=refresh_token)
    except AuthError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail={"message_key": exc.message_key}
        ) from exc
    _set_refresh_cookie(response, tokens.refresh_token)
    return _token_response(tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
