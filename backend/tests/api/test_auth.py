from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import Role, User


async def _create_user(
    db_session: AsyncSession,
    *,
    email: str = "alice@example.com",
    password: str = "password123",
    role: Role = Role.EMPLOYEE,
) -> User:
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name="Alice Example",
        role=role,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def test_login_succeeds_with_correct_credentials(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _create_user(db_session)

    response = await client.post(
        "/api/v1/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "alice@example.com"
    assert body["access_token"]
    assert "refresh_token" in response.cookies


async def test_login_fails_with_wrong_password(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _create_user(db_session)

    response = await client.post(
        "/api/v1/auth/login", json={"email": "alice@example.com", "password": "wrong"}
    )

    assert response.status_code == 401
    assert response.json()["detail"]["message_key"] == "auth.invalid_credentials"


async def test_login_fails_for_unknown_email(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "password123"}
    )

    assert response.status_code == 401
    assert response.json()["detail"]["message_key"] == "auth.invalid_credentials"


async def test_refresh_issues_a_new_access_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _create_user(db_session)
    login_response = await client.post(
        "/api/v1/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200

    refresh_response = await client.post("/api/v1/auth/refresh")

    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"]


async def test_refresh_without_cookie_is_unauthorized(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    assert response.json()["detail"]["message_key"] == "auth.missing_token"


async def test_logout_clears_the_refresh_cookie(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _create_user(db_session)
    await client.post(
        "/api/v1/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )

    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 204
