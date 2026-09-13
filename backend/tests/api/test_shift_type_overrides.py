from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Role
from tests.api.scheduling_helpers import auth_headers, create_shift_types, create_user, login


async def test_employee_cannot_upsert_override(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shift_types = await create_shift_types(db_session)
    await create_user(db_session, email="alice4@example.com", role=Role.EMPLOYEE)
    token = await login(client, "alice4@example.com")

    response = await client.put(
        f"/api/v1/shift-types/{shift_types['EVENING'].id}/overrides/FRI",
        json={
            "start_time": "15:00:00",
            "end_time": "22:00:00",
            "min_staff": 1,
            "required_staff": 1,
            "max_staff": 1,
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 403


async def test_admin_can_set_override_and_it_applies_to_generated_slots(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shift_types = await create_shift_types(db_session)
    await create_user(db_session, email="bob4@example.com", role=Role.ADMIN)
    token = await login(client, "bob4@example.com")
    headers = auth_headers(token)

    override_response = await client.put(
        f"/api/v1/shift-types/{shift_types['EVENING'].id}/overrides/FRI",
        json={
            "start_time": "15:00:00",
            "end_time": "22:00:00",
            "min_staff": 1,
            "required_staff": 1,
            "max_staff": 1,
        },
        headers=headers,
    )
    assert override_response.status_code == 200
    assert override_response.json()["weekday"] == "FRI"

    read_response = await client.get("/api/v1/shift-types", headers=headers)
    evening = next(s for s in read_response.json() if s["code"] == "EVENING")
    assert len(evening["overrides"]) == 1
    assert evening["overrides"][0]["start_time"] == "15:00:00"

    # 2027-01-01 is a Friday - the generated slot for it should carry the
    # override's time, not EVENING's own 15:00-23:00 default end time.
    period_response = await client.post(
        "/api/v1/periods", json={"year": 2027, "month": 1}, headers=headers
    )
    period_id = period_response.json()["id"]
    slots = (await client.get(f"/api/v1/periods/{period_id}/slots", headers=headers)).json()
    friday_evening = next(
        s
        for s in slots
        if s["date"] == "2027-01-01" and s["shift_type_id"] == str(shift_types["EVENING"].id)
    )
    assert friday_evening["end_time"] == "22:00:00"

    # A non-Friday EVENING slot keeps the ShiftType's own default time.
    other_evening = next(
        s
        for s in slots
        if s["date"] == "2027-01-02" and s["shift_type_id"] == str(shift_types["EVENING"].id)
    )
    assert other_evening["end_time"] == "23:00:00"


async def test_admin_can_delete_override(client: AsyncClient, db_session: AsyncSession) -> None:
    shift_types = await create_shift_types(db_session)
    await create_user(db_session, email="carol4@example.com", role=Role.ADMIN)
    token = await login(client, "carol4@example.com")
    headers = auth_headers(token)

    await client.put(
        f"/api/v1/shift-types/{shift_types['EVENING'].id}/overrides/FRI",
        json={
            "start_time": "15:00:00",
            "end_time": "22:00:00",
            "min_staff": 1,
            "required_staff": 1,
            "max_staff": 1,
        },
        headers=headers,
    )

    delete_response = await client.delete(
        f"/api/v1/shift-types/{shift_types['EVENING'].id}/overrides/FRI", headers=headers
    )
    assert delete_response.status_code == 204

    read_response = await client.get("/api/v1/shift-types", headers=headers)
    evening = next(s for s in read_response.json() if s["code"] == "EVENING")
    assert evening["overrides"] == []
