from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Role
from tests.api.scheduling_helpers import auth_headers, create_user, login


async def _create_criterion(
    client: AsyncClient,
    token: str,
    *,
    code: str,
    weight: str,
    is_active: bool = True,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/score-criteria",
        json={
            "code": code,
            "name_pl": code,
            "name_en": code,
            "weight": weight,
            "is_active": is_active,
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.json()
    return dict(response.json())


# --- criteria: admin manages, manager can only read -----------------------


async def test_employee_cannot_list_score_criteria(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="amy4@example.com", role=Role.EMPLOYEE)
    token = await login(client, "amy4@example.com")

    response = await client.get("/api/v1/score-criteria", headers=auth_headers(token))

    assert response.status_code == 403


async def test_manager_can_list_but_not_create_score_criteria(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="ben4@example.com", role=Role.MANAGER)
    token = await login(client, "ben4@example.com")

    list_response = await client.get("/api/v1/score-criteria", headers=auth_headers(token))
    assert list_response.status_code == 200

    create_response = await client.post(
        "/api/v1/score-criteria",
        json={"code": "SPEED", "name_pl": "Szybkosc", "name_en": "Speed", "weight": "1.0"},
        headers=auth_headers(token),
    )
    assert create_response.status_code == 403


async def test_admin_can_create_a_criterion_at_full_weight(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="cleo4@example.com", role=Role.ADMIN)
    token = await login(client, "cleo4@example.com")

    body = await _create_criterion(client, token, code="RELIABILITY", weight="1.0")

    assert body["is_active"] is True
    assert body["scale_min"] == 1
    assert body["scale_max"] == 5


async def test_creating_a_second_active_criterion_that_breaks_the_sum_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="don4@example.com", role=Role.ADMIN)
    token = await login(client, "don4@example.com")
    await _create_criterion(client, token, code="RELIABILITY", weight="1.0")

    response = await client.post(
        "/api/v1/score-criteria",
        json={
            "code": "SPEED",
            "name_pl": "Szybkosc",
            "name_en": "Speed",
            "weight": "0.6",
            "is_active": True,
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["message_key"] == "score_criterion.weights_must_sum_to_one"
    assert detail["params"]["total"] == "1.6000"


async def test_new_inactive_criterion_does_not_need_to_balance(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="erin4@example.com", role=Role.ADMIN)
    token = await login(client, "erin4@example.com")
    await _create_criterion(client, token, code="RELIABILITY", weight="1.0")

    response = await client.post(
        "/api/v1/score-criteria",
        json={"code": "SPEED", "name_pl": "Szybkosc", "name_en": "Speed", "weight": "0.6"},
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    assert response.json()["is_active"] is False


async def test_bulk_weight_update_rebalances_multiple_criteria_atomically(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="frank4@example.com", role=Role.ADMIN)
    token = await login(client, "frank4@example.com")
    headers = auth_headers(token)
    # Created inactive, since a lone 0.6 or 0.4 wouldn't sum to 1.0 on its own -
    # both are brought active together by the bulk call below.
    a = await _create_criterion(client, token, code="A", weight="0.6", is_active=False)
    b = await _create_criterion(client, token, code="B", weight="0.4", is_active=False)

    activate_response = await client.put(
        "/api/v1/score-criteria/weights",
        json={
            "items": [
                {"id": a["id"], "weight": "0.6", "is_active": True},
                {"id": b["id"], "weight": "0.4", "is_active": True},
            ]
        },
        headers=headers,
    )
    assert activate_response.status_code == 200

    response = await client.put(
        "/api/v1/score-criteria/weights",
        json={
            "items": [
                {"id": a["id"], "weight": "0.5", "is_active": True},
                {"id": b["id"], "weight": "0.5", "is_active": True},
            ]
        },
        headers=headers,
    )

    assert response.status_code == 200
    weights = {row["id"]: row["weight"] for row in response.json()}
    assert weights[a["id"]] == "0.5000"
    assert weights[b["id"]] == "0.5000"


async def test_bulk_weight_update_rejects_a_total_other_than_one(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="gina4@example.com", role=Role.ADMIN)
    token = await login(client, "gina4@example.com")
    a = await _create_criterion(client, token, code="A", weight="1.0")

    response = await client.put(
        "/api/v1/score-criteria/weights",
        json={"items": [{"id": a["id"], "weight": "0.9", "is_active": True}]},
        headers=auth_headers(token),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["message_key"] == "score_criterion.weights_must_sum_to_one"


async def test_deactivating_a_criterion_that_would_break_the_sum_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="hank4@example.com", role=Role.ADMIN)
    token = await login(client, "hank4@example.com")
    headers = auth_headers(token)
    a = await _create_criterion(client, token, code="A", weight="0.6", is_active=False)
    b = await _create_criterion(client, token, code="B", weight="0.4", is_active=False)
    await client.put(
        "/api/v1/score-criteria/weights",
        json={
            "items": [
                {"id": a["id"], "weight": "0.6", "is_active": True},
                {"id": b["id"], "weight": "0.4", "is_active": True},
            ]
        },
        headers=headers,
    )

    response = await client.post(f"/api/v1/score-criteria/{a['id']}/deactivate", headers=headers)

    assert response.status_code == 422
    assert response.json()["detail"]["message_key"] == "score_criterion.weights_must_sum_to_one"


async def test_renaming_a_criterion_does_not_require_weights_to_sum_to_one(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="iris4@example.com", role=Role.ADMIN)
    token = await login(client, "iris4@example.com")
    a = await _create_criterion(client, token, code="A", weight="1.0")

    response = await client.patch(
        f"/api/v1/score-criteria/{a['id']}",
        json={"name_en": "A renamed", "description": "updated"},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["name_en"] == "A renamed"


# --- scores: manager+admin only, employee always blocked -------------------


async def test_employee_is_blocked_from_every_score_endpoint(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="admin4a@example.com", role=Role.ADMIN)
    admin_token = await login(client, "admin4a@example.com")
    criterion = await _create_criterion(client, admin_token, code="A", weight="1.0")
    target = await create_user(db_session, email="target4@example.com", role=Role.EMPLOYEE)

    employee_token = await login(client, "target4@example.com")
    headers = auth_headers(employee_token)

    assert (await client.get("/api/v1/scores/grid", headers=headers)).status_code == 403
    assert (
        await client.get(f"/api/v1/users/{target.id}/scores/history", headers=headers)
    ).status_code == 403
    assert (
        await client.post(
            f"/api/v1/users/{target.id}/scores",
            json={"criterion_id": criterion["id"], "value": 5},
            headers=headers,
        )
    ).status_code == 403


async def test_manager_can_set_a_score_and_see_it_in_the_grid(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="admin4b@example.com", role=Role.ADMIN)
    admin_token = await login(client, "admin4b@example.com")
    criterion = await _create_criterion(client, admin_token, code="RELIABILITY", weight="1.0")

    await create_user(db_session, email="jill4@example.com", role=Role.MANAGER)
    token = await login(client, "jill4@example.com")
    headers = auth_headers(token)
    employee = await create_user(
        db_session, email="kim4@example.com", role=Role.EMPLOYEE, full_name="Kim"
    )

    set_response = await client.post(
        f"/api/v1/users/{employee.id}/scores",
        json={"criterion_id": criterion["id"], "value": 4, "note": "solid month"},
        headers=headers,
    )
    assert set_response.status_code == 201
    assert set_response.json()["value"] == 4

    grid_response = await client.get("/api/v1/scores/grid", headers=headers)
    assert grid_response.status_code == 200
    row = next(r for r in grid_response.json() if r["user_id"] == str(employee.id))
    assert row["entries"][0]["value"] == 4
    assert row["composite"] == 75.0  # (4-1)/4 * 100 * weight 1.0


async def test_scoring_an_inactive_criterion_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="admin4c@example.com", role=Role.ADMIN)
    admin_token = await login(client, "admin4c@example.com")
    criterion = await _create_criterion(
        client, admin_token, code="RELIABILITY", weight="0.5", is_active=False
    )

    await create_user(db_session, email="liam4@example.com", role=Role.MANAGER)
    token = await login(client, "liam4@example.com")
    headers = auth_headers(token)
    employee = await create_user(db_session, email="mia4@example.com", role=Role.EMPLOYEE)

    response = await client.post(
        f"/api/v1/users/{employee.id}/scores",
        json={"criterion_id": criterion["id"], "value": 3},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["message_key"] == "score.criterion_inactive"


async def test_score_changes_are_versioned_never_overwritten(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="admin4d@example.com", role=Role.ADMIN)
    admin_token = await login(client, "admin4d@example.com")
    criterion = await _create_criterion(client, admin_token, code="RELIABILITY", weight="1.0")

    await create_user(db_session, email="noah4@example.com", role=Role.MANAGER)
    token = await login(client, "noah4@example.com")
    headers = auth_headers(token)
    employee = await create_user(db_session, email="opal4@example.com", role=Role.EMPLOYEE)

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    await client.post(
        f"/api/v1/users/{employee.id}/scores",
        json={
            "criterion_id": criterion["id"],
            "value": 2,
            "effective_from": yesterday,
            "note": "initial",
        },
        headers=headers,
    )
    await client.post(
        f"/api/v1/users/{employee.id}/scores",
        json={"criterion_id": criterion["id"], "value": 5, "note": "improved"},
        headers=headers,
    )

    history_response = await client.get(
        f"/api/v1/users/{employee.id}/scores/history", headers=headers
    )
    assert history_response.status_code == 200
    entries = history_response.json()
    assert len(entries) == 2
    latest, previous = entries[0], entries[1]
    assert latest["value"] == 5
    assert latest["previous_value"] == 2
    assert latest["note"] == "improved"
    assert previous["value"] == 2
    assert previous["previous_value"] is None

    grid_response = await client.get("/api/v1/scores/grid", headers=headers)
    row = next(r for r in grid_response.json() if r["user_id"] == str(employee.id))
    assert row["entries"][0]["value"] == 5  # today's effective value, not the superseded one


# --- privacy: no employee-facing surface ever includes a score -------------


async def test_user_endpoints_never_include_score_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="admin4@example.com", role=Role.ADMIN)
    admin_token = await login(client, "admin4@example.com")
    admin_headers = auth_headers(admin_token)
    criterion = await _create_criterion(client, admin_token, code="RELIABILITY", weight="1.0")
    employee = await create_user(db_session, email="pat4@example.com", role=Role.EMPLOYEE)
    await client.post(
        f"/api/v1/users/{employee.id}/scores",
        json={"criterion_id": criterion["id"], "value": 5},
        headers=admin_headers,
    )

    employee_token = await login(client, "pat4@example.com")
    own_profile = await client.get("/api/v1/users/me", headers=auth_headers(employee_token))
    assert own_profile.status_code == 200
    assert "score" not in own_profile.text.lower()

    admin_user_list = await client.get("/api/v1/users", headers=admin_headers)
    assert admin_user_list.status_code == 200
    assert "score" not in admin_user_list.text.lower()
