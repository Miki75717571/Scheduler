import calendar
from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Role
from tests.api.scheduling_helpers import auth_headers, create_shift_types, create_user, login


def _expected_slot_count(year: int, month: int) -> int:
    days_in_month = calendar.monthrange(year, month)[1]
    morning_evening = days_in_month * 2  # active every day
    weekend_days = sum(
        1 for day in range(1, days_in_month + 1) if date(year, month, day).weekday() >= 5
    )
    return morning_evening + weekend_days  # + MIDDAY on Sat/Sun


async def test_employee_cannot_create_period(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_user(db_session, email="amy@example.com", role=Role.EMPLOYEE)
    token = await login(client, "amy@example.com")

    response = await client.post(
        "/api/v1/periods", json={"year": 2027, "month": 1}, headers=auth_headers(token)
    )

    assert response.status_code == 403


async def test_manager_creates_period_and_slots_are_generated(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="ben@example.com", role=Role.MANAGER)
    token = await login(client, "ben@example.com")

    create_response = await client.post(
        "/api/v1/periods", json={"year": 2027, "month": 1}, headers=auth_headers(token)
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["state"] == "DRAFT"
    period_id = body["id"]

    slots_response = await client.get(
        f"/api/v1/periods/{period_id}/slots", headers=auth_headers(token)
    )
    assert slots_response.status_code == 200
    slots = slots_response.json()
    assert len(slots) == _expected_slot_count(2027, 1)


async def test_creating_duplicate_period_conflicts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="cleo@example.com", role=Role.ADMIN)
    token = await login(client, "cleo@example.com")

    await client.post(
        "/api/v1/periods", json={"year": 2027, "month": 2}, headers=auth_headers(token)
    )
    second = await client.post(
        "/api/v1/periods", json={"year": 2027, "month": 2}, headers=auth_headers(token)
    )

    assert second.status_code == 409
    assert second.json()["detail"]["message_key"] == "period.already_exists"


async def test_legal_state_transitions_succeed_in_order(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="don@example.com", role=Role.MANAGER)
    token = await login(client, "don@example.com")
    headers = auth_headers(token)

    period_id = (
        await client.post("/api/v1/periods", json={"year": 2027, "month": 3}, headers=headers)
    ).json()["id"]

    for target in ("COLLECTING", "LOCKED", "GENERATED", "PUBLISHED"):
        response = await client.patch(
            f"/api/v1/periods/{period_id}/state", json={"state": target}, headers=headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["state"] == target

    published = (await client.get(f"/api/v1/periods/{period_id}", headers=headers)).json()
    assert published["published_at"] is not None
    assert published["published_by_user_id"] is not None


async def test_skipping_a_state_is_rejected(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="edna@example.com", role=Role.MANAGER)
    token = await login(client, "edna@example.com")
    headers = auth_headers(token)

    period_id = (
        await client.post("/api/v1/periods", json={"year": 2027, "month": 4}, headers=headers)
    ).json()["id"]

    response = await client.patch(
        f"/api/v1/periods/{period_id}/state", json={"state": "LOCKED"}, headers=headers
    )

    assert response.status_code == 409
    assert response.json()["detail"]["message_key"] == "period.illegal_transition"


async def test_moving_backward_is_rejected(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="fred@example.com", role=Role.MANAGER)
    token = await login(client, "fred@example.com")
    headers = auth_headers(token)

    period_id = (
        await client.post("/api/v1/periods", json={"year": 2027, "month": 5}, headers=headers)
    ).json()["id"]
    await client.patch(
        f"/api/v1/periods/{period_id}/state", json={"state": "COLLECTING"}, headers=headers
    )
    await client.patch(
        f"/api/v1/periods/{period_id}/state", json={"state": "LOCKED"}, headers=headers
    )

    response = await client.patch(
        f"/api/v1/periods/{period_id}/state", json={"state": "COLLECTING"}, headers=headers
    )

    assert response.status_code == 409
    assert response.json()["detail"]["message_key"] == "period.illegal_transition"


async def test_employee_cannot_transition_period_state(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="greg@example.com", role=Role.MANAGER)
    manager_token = await login(client, "greg@example.com")
    period_id = (
        await client.post(
            "/api/v1/periods", json={"year": 2027, "month": 6}, headers=auth_headers(manager_token)
        )
    ).json()["id"]

    await create_user(db_session, email="hana@example.com", role=Role.EMPLOYEE, full_name="Hana")
    employee_token = await login(client, "hana@example.com")

    response = await client.patch(
        f"/api/v1/periods/{period_id}/state",
        json={"state": "COLLECTING"},
        headers=auth_headers(employee_token),
    )

    assert response.status_code == 403


async def test_manager_can_edit_slot_staffing_and_close_it(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="iris@example.com", role=Role.MANAGER)
    token = await login(client, "iris@example.com")
    headers = auth_headers(token)

    period_id = (
        await client.post("/api/v1/periods", json={"year": 2027, "month": 7}, headers=headers)
    ).json()["id"]
    slot = (await client.get(f"/api/v1/periods/{period_id}/slots", headers=headers)).json()[0]

    response = await client.patch(
        f"/api/v1/periods/{period_id}/slots/{slot['id']}",
        json={
            "required_staff": 4,
            "min_staff": 2,
            "max_staff": 5,
            "is_closed": True,
            "note": "Holiday",
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["required_staff"] == 4
    assert body["is_closed"] is True
    assert body["note"] == "Holiday"


async def test_employee_cannot_edit_slot(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="jack@example.com", role=Role.MANAGER)
    manager_token = await login(client, "jack@example.com")
    period_id = (
        await client.post(
            "/api/v1/periods", json={"year": 2027, "month": 8}, headers=auth_headers(manager_token)
        )
    ).json()["id"]
    slot = (
        await client.get(f"/api/v1/periods/{period_id}/slots", headers=auth_headers(manager_token))
    ).json()[0]

    await create_user(db_session, email="kate@example.com", role=Role.EMPLOYEE, full_name="Kate")
    employee_token = await login(client, "kate@example.com")

    response = await client.patch(
        f"/api/v1/periods/{period_id}/slots/{slot['id']}",
        json={"required_staff": 9},
        headers=auth_headers(employee_token),
    )

    assert response.status_code == 403


async def test_transitioning_to_collecting_creates_submissions_for_active_users(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="liam@example.com", role=Role.MANAGER)
    manager_token = await login(client, "liam@example.com")
    headers = auth_headers(manager_token)
    await create_user(db_session, email="maya@example.com", role=Role.EMPLOYEE, full_name="Maya")

    period_id = (
        await client.post("/api/v1/periods", json={"year": 2027, "month": 9}, headers=headers)
    ).json()["id"]
    await client.patch(
        f"/api/v1/periods/{period_id}/state", json={"state": "COLLECTING"}, headers=headers
    )

    tracker_response = await client.get(
        f"/api/v1/periods/{period_id}/availability/tracker", headers=headers
    )
    assert tracker_response.status_code == 200
    entries = tracker_response.json()
    emails_status = {e["full_name"]: e["status"] for e in entries}
    assert emails_status["Maya"] == "NOT_STARTED"
