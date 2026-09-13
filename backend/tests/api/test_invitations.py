import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import Role, User
from app.services import email_service


async def _create_user(
    db_session: AsyncSession, *, email: str, password: str = "password123", role: Role
) -> User:
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name="Test User",
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


@pytest.fixture
def captured_email(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    captured: dict[str, str] = {}

    def fake_send(self: email_service.EmailService, *, to: str, accept_url: str) -> None:
        captured["to"] = to
        captured["accept_url"] = accept_url

    monkeypatch.setattr(email_service.EmailService, "send_invitation_email", fake_send)
    return captured


async def test_employee_cannot_create_invitation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _create_user(db_session, email="ivy@example.com", role=Role.EMPLOYEE)
    token = await _login(client, "ivy@example.com")

    response = await client.post(
        "/api/v1/invitations",
        json={"email": "new@example.com", "role": "EMPLOYEE"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


async def test_manager_cannot_create_invitation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _create_user(db_session, email="jack@example.com", role=Role.MANAGER)
    token = await _login(client, "jack@example.com")

    response = await client.post(
        "/api/v1/invitations",
        json={"email": "new@example.com", "role": "EMPLOYEE"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


async def test_admin_can_invite_and_invitee_can_accept_and_log_in(
    client: AsyncClient, db_session: AsyncSession, captured_email: dict[str, str]
) -> None:
    await _create_user(db_session, email="kate@example.com", role=Role.ADMIN)
    token = await _login(client, "kate@example.com")

    create_response = await client.post(
        "/api/v1/invitations",
        json={"email": "newhire@example.com", "role": "EMPLOYEE"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    assert captured_email["to"] == "newhire@example.com"

    raw_token = captured_email["accept_url"].split("token=")[1]

    preview_response = await client.get(f"/api/v1/invitations/{raw_token}")
    assert preview_response.status_code == 200
    assert preview_response.json()["email"] == "newhire@example.com"

    accept_response = await client.post(
        "/api/v1/invitations/accept",
        json={"token": raw_token, "full_name": "New Hire", "password": "brandnewpassword"},
    )
    assert accept_response.status_code == 200
    assert accept_response.json()["role"] == "EMPLOYEE"

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "newhire@example.com", "password": "brandnewpassword"},
    )
    assert login_response.status_code == 200


async def test_invitation_cannot_be_accepted_twice(
    client: AsyncClient, db_session: AsyncSession, captured_email: dict[str, str]
) -> None:
    await _create_user(db_session, email="leo@example.com", role=Role.ADMIN)
    token = await _login(client, "leo@example.com")

    await client.post(
        "/api/v1/invitations",
        json={"email": "second@example.com", "role": "EMPLOYEE"},
        headers={"Authorization": f"Bearer {token}"},
    )
    raw_token = captured_email["accept_url"].split("token=")[1]

    first = await client.post(
        "/api/v1/invitations/accept",
        json={"token": raw_token, "full_name": "Second Hire", "password": "anotherpassword"},
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/invitations/accept",
        json={"token": raw_token, "full_name": "Second Hire", "password": "anotherpassword"},
    )
    assert second.status_code == 400
    assert second.json()["detail"]["message_key"] == "invitation.already_used"


async def test_invalid_invitation_token_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/api/v1/invitations/not-a-real-token")

    assert response.status_code == 400
    assert response.json()["detail"]["message_key"] == "invitation.not_found"


async def test_accept_url_is_present_when_using_console_provider(
    client: AsyncClient, db_session: AsyncSession, captured_email: dict[str, str]
) -> None:
    assert settings.email_provider == "console"  # sanity: what the test suite runs as
    await _create_user(db_session, email="olive@example.com", role=Role.ADMIN)
    token = await _login(client, "olive@example.com")

    response = await client.post(
        "/api/v1/invitations",
        json={"email": "devcheck@example.com", "role": "EMPLOYEE"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["accept_url"] == captured_email["accept_url"]


async def test_accept_url_is_present_even_in_production_when_still_on_console(
    client: AsyncClient,
    db_session: AsyncSession,
    captured_email: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The owner deliberately stays on the console email provider past
    development (CLAUDE.md JOB 8) - the link must still be visible then,
    since app_env alone no longer decides this."""
    await _create_user(db_session, email="pete@example.com", role=Role.ADMIN)
    token = await _login(client, "pete@example.com")

    monkeypatch.setattr(settings, "app_env", "production")
    response = await client.post(
        "/api/v1/invitations",
        json={"email": "prodcheck@example.com", "role": "EMPLOYEE"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["accept_url"] == captured_email["accept_url"]


async def test_accept_url_is_absent_when_using_resend(
    client: AsyncClient,
    db_session: AsyncSession,
    captured_email: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _create_user(db_session, email="quinn2@example.com", role=Role.ADMIN)
    token = await _login(client, "quinn2@example.com")

    monkeypatch.setattr(settings, "email_provider", "resend")
    response = await client.post(
        "/api/v1/invitations",
        json={"email": "realmail@example.com", "role": "EMPLOYEE"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["accept_url"] is None
    # The invite still works end-to-end - only the response field is gated.
    assert captured_email["accept_url"] is not None


async def test_employee_cannot_list_invitations(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _create_user(db_session, email="rex@example.com", role=Role.EMPLOYEE)
    token = await _login(client, "rex@example.com")

    response = await client.get("/api/v1/invitations", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


async def test_admin_can_list_resend_and_revoke_invitations(
    client: AsyncClient, db_session: AsyncSession, captured_email: dict[str, str]
) -> None:
    await _create_user(db_session, email="sam@example.com", role=Role.ADMIN)
    token = await _login(client, "sam@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/api/v1/invitations",
        json={"email": "future@example.com", "role": "EMPLOYEE"},
        headers=headers,
    )
    invitation_id = create_response.json()["id"]
    original_accept_url = captured_email["accept_url"]

    list_response = await client.get("/api/v1/invitations", headers=headers)
    assert list_response.status_code == 200
    listed = next(i for i in list_response.json() if i["id"] == invitation_id)
    assert listed["status"] == "PENDING"

    resend_response = await client.post(
        f"/api/v1/invitations/{invitation_id}/resend", headers=headers
    )
    assert resend_response.status_code == 200
    assert resend_response.json()["accept_url"] != original_accept_url
    old_token = original_accept_url.split("token=")[1]
    stale_accept = await client.post(
        "/api/v1/invitations/accept",
        json={"token": old_token, "full_name": "Late", "password": "somepassword"},
    )
    assert stale_accept.status_code == 400
    assert stale_accept.json()["detail"]["message_key"] == "invitation.not_found"

    revoke_response = await client.post(
        f"/api/v1/invitations/{invitation_id}/revoke", headers=headers
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["status"] == "REVOKED"

    new_token = captured_email["accept_url"].split("token=")[1]
    revoked_accept = await client.post(
        "/api/v1/invitations/accept",
        json={"token": new_token, "full_name": "Too Late", "password": "somepassword"},
    )
    assert revoked_accept.status_code == 400
    assert revoked_accept.json()["detail"]["message_key"] == "invitation.revoked"


async def test_cannot_invite_an_already_registered_email(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _create_user(db_session, email="admin@example.com", role=Role.ADMIN)
    await _create_user(db_session, email="existing@example.com", role=Role.EMPLOYEE)
    token = await _login(client, "admin@example.com")

    response = await client.post(
        "/api/v1/invitations",
        json={"email": "existing@example.com", "role": "EMPLOYEE"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["message_key"] == "invitation.email_already_registered"
