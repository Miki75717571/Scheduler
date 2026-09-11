from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import Role, User


async def _create_user(
    db_session: AsyncSession,
    *,
    email: str,
    password: str = "password123",
    role: Role = Role.EMPLOYEE,
    full_name: str = "Test User",
) -> User:
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _login(client: AsyncClient, email: str, password: str = "password123") -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return str(response.json()["access_token"])


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_me_returns_the_current_user(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_user(db_session, email="bob@example.com")
    token = await _login(client, "bob@example.com")

    response = await client.get("/api/v1/users/me", headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json()["email"] == "bob@example.com"


async def test_request_without_token_is_unauthorized(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me")

    assert response.status_code == 401
    assert response.json()["detail"]["message_key"] == "auth.missing_token"


async def test_employee_cannot_list_users(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_user(db_session, email="carol@example.com", role=Role.EMPLOYEE)
    token = await _login(client, "carol@example.com")

    response = await client.get("/api/v1/users", headers=_auth_headers(token))

    assert response.status_code == 403
    assert response.json()["detail"]["message_key"] == "auth.forbidden"


async def test_manager_cannot_list_users(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_user(db_session, email="dana@example.com", role=Role.MANAGER)
    token = await _login(client, "dana@example.com")

    response = await client.get("/api/v1/users", headers=_auth_headers(token))

    assert response.status_code == 403


async def test_admin_can_list_users(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_user(db_session, email="erin@example.com", role=Role.ADMIN)
    await _create_user(db_session, email="frank@example.com", role=Role.EMPLOYEE)
    token = await _login(client, "erin@example.com")

    response = await client.get("/api/v1/users", headers=_auth_headers(token))

    assert response.status_code == 200
    emails = {u["email"] for u in response.json()}
    assert {"erin@example.com", "frank@example.com"} <= emails


async def test_employee_cannot_deactivate_another_user(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    target = await _create_user(db_session, email="greg@example.com", role=Role.EMPLOYEE)
    await _create_user(db_session, email="hana@example.com", role=Role.EMPLOYEE, full_name="Hana")
    token = await _login(client, "hana@example.com")

    response = await client.post(
        f"/api/v1/users/{target.id}/deactivate", headers=_auth_headers(token)
    )

    assert response.status_code == 403


async def test_manager_cannot_deactivate_a_user(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    target = await _create_user(db_session, email="ian@example.com", role=Role.EMPLOYEE)
    await _create_user(db_session, email="jill@example.com", role=Role.MANAGER, full_name="Jill")
    token = await _login(client, "jill@example.com")

    response = await client.post(
        f"/api/v1/users/{target.id}/deactivate", headers=_auth_headers(token)
    )

    assert response.status_code == 403


async def test_admin_can_deactivate_a_user(client: AsyncClient, db_session: AsyncSession) -> None:
    target = await _create_user(db_session, email="kyle@example.com", role=Role.EMPLOYEE)
    await _create_user(db_session, email="lena@example.com", role=Role.ADMIN, full_name="Lena")
    token = await _login(client, "lena@example.com")

    response = await client.post(
        f"/api/v1/users/{target.id}/deactivate", headers=_auth_headers(token)
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_deactivated_user_cannot_log_in(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _create_user(db_session, email="mona@example.com", role=Role.EMPLOYEE)
    await _create_user(db_session, email="nick@example.com", role=Role.ADMIN, full_name="Nick")
    admin_token = await _login(client, "nick@example.com")

    users = (await client.get("/api/v1/users", headers=_auth_headers(admin_token))).json()
    mona_id = next(u["id"] for u in users if u["email"] == "mona@example.com")
    await client.post(f"/api/v1/users/{mona_id}/deactivate", headers=_auth_headers(admin_token))

    response = await client.post(
        "/api/v1/auth/login", json={"email": "mona@example.com", "password": "password123"}
    )
    assert response.status_code == 401
