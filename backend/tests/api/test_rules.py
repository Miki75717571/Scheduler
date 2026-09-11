from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Role
from tests.api.scheduling_helpers import auth_headers, create_user, login


async def test_employee_cannot_list_rules(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_user(db_session, email="amy3@example.com", role=Role.EMPLOYEE)
    token = await login(client, "amy3@example.com")

    response = await client.get("/api/v1/rules", headers=auth_headers(token))

    assert response.status_code == 403


async def test_manager_cannot_create_rule(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_user(db_session, email="ben3@example.com", role=Role.MANAGER)
    token = await login(client, "ben3@example.com")

    response = await client.post(
        "/api/v1/rules",
        json={
            "code": "min_7",
            "name_pl": "Minimum 7",
            "name_en": "Minimum 7",
            "type": "MIN_AVAILABILITY_COUNT",
            "params": {"n": 7},
            "phase": "AVAILABILITY",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 403


async def test_admin_can_create_rule(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_user(db_session, email="cleo3@example.com", role=Role.ADMIN)
    token = await login(client, "cleo3@example.com")

    response = await client.post(
        "/api/v1/rules",
        json={
            "code": "min_7",
            "name_pl": "Minimum 7 zmian",
            "name_en": "Minimum 7 shifts",
            "type": "MIN_AVAILABILITY_COUNT",
            "params": {"n": 7},
            "phase": "AVAILABILITY",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["severity"] == "HARD"
    assert body["scope"] == "GLOBAL"


async def test_creating_rule_with_malformed_params_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="don3@example.com", role=Role.ADMIN)
    token = await login(client, "don3@example.com")

    response = await client.post(
        "/api/v1/rules",
        json={
            "code": "bad_rule",
            "name_pl": "Zla regula",
            "name_en": "Bad rule",
            "type": "MIN_AVAILABILITY_IN_SET",
            "params": {"n": 1, "weekday": "NOT_A_DAY", "shift": "EVENING"},
            "phase": "AVAILABILITY",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["message_key"] == "rule.invalid_params"


async def test_creating_rule_with_duplicate_code_conflicts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="erin3@example.com", role=Role.ADMIN)
    token = await login(client, "erin3@example.com")
    headers = auth_headers(token)
    payload = {
        "code": "dup_rule",
        "name_pl": "Duplikat",
        "name_en": "Duplicate",
        "type": "MIN_AVAILABILITY_COUNT",
        "params": {"n": 1},
        "phase": "AVAILABILITY",
    }
    await client.post("/api/v1/rules", json=payload, headers=headers)

    response = await client.post("/api/v1/rules", json=payload, headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"]["message_key"] == "rule.code_already_exists"


async def test_admin_can_update_rule_params(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_user(db_session, email="frank3@example.com", role=Role.ADMIN)
    token = await login(client, "frank3@example.com")
    headers = auth_headers(token)
    create_response = await client.post(
        "/api/v1/rules",
        json={
            "code": "min_weekend",
            "name_pl": "Minimum weekend",
            "name_en": "Minimum weekend",
            "type": "MIN_AVAILABILITY_WEEKEND",
            "params": {"n": 1},
            "phase": "AVAILABILITY",
        },
        headers=headers,
    )
    rule_id = create_response.json()["id"]

    response = await client.patch(
        f"/api/v1/rules/{rule_id}", json={"params": {"n": 2}}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["params"] == {"n": 2}
