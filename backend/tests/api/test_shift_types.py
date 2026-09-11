from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Role
from tests.api.scheduling_helpers import auth_headers, create_shift_types, create_user, login


async def test_any_authenticated_user_can_list_shift_types(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="alice@example.com", role=Role.EMPLOYEE)
    token = await login(client, "alice@example.com")

    response = await client.get("/api/v1/shift-types", headers=auth_headers(token))

    assert response.status_code == 200
    codes = {s["code"] for s in response.json()}
    assert codes == {"MORNING", "EVENING", "MIDDAY"}


async def test_employee_cannot_create_shift_type(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="bob@example.com", role=Role.EMPLOYEE)
    token = await login(client, "bob@example.com")

    response = await client.post(
        "/api/v1/shift-types",
        json={
            "code": "NIGHT",
            "name_pl": "Noc",
            "name_en": "Night",
            "start_time": "23:00:00",
            "end_time": "23:59:00",
            "active_weekdays": 127,
            "default_required_staff": 1,
            "default_min_staff": 1,
            "default_max_staff": 1,
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 403


async def test_manager_cannot_create_shift_type(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="carol@example.com", role=Role.MANAGER)
    token = await login(client, "carol@example.com")

    response = await client.post(
        "/api/v1/shift-types",
        json={
            "code": "NIGHT",
            "name_pl": "Noc",
            "name_en": "Night",
            "start_time": "23:00:00",
            "end_time": "23:59:00",
            "active_weekdays": 127,
            "default_required_staff": 1,
            "default_min_staff": 1,
            "default_max_staff": 1,
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 403


async def test_admin_can_create_and_update_shift_type(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="dana@example.com", role=Role.ADMIN)
    token = await login(client, "dana@example.com")

    create_response = await client.post(
        "/api/v1/shift-types",
        json={
            "code": "FRIDAY_LATE",
            "name_pl": "Piatek pozny",
            "name_en": "Friday late",
            "start_time": "20:00:00",
            "end_time": "23:59:00",
            "active_weekdays": 16,  # Friday only
            "default_required_staff": 1,
            "default_min_staff": 1,
            "default_max_staff": 2,
        },
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201
    shift_type_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/api/v1/shift-types/{shift_type_id}",
        json={"default_required_staff": 2},
        headers=auth_headers(token),
    )
    assert update_response.status_code == 200
    assert update_response.json()["default_required_staff"] == 2


async def test_creating_shift_type_with_duplicate_code_conflicts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="erin@example.com", role=Role.ADMIN)
    token = await login(client, "erin@example.com")

    response = await client.post(
        "/api/v1/shift-types",
        json={
            "code": "MORNING",
            "name_pl": "Rano 2",
            "name_en": "Morning 2",
            "start_time": "06:00:00",
            "end_time": "14:00:00",
            "active_weekdays": 127,
            "default_required_staff": 1,
            "default_min_staff": 1,
            "default_max_staff": 1,
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["message_key"] == "shift_type.code_already_exists"


async def test_creating_shift_type_with_invalid_staff_levels_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="frank@example.com", role=Role.ADMIN)
    token = await login(client, "frank@example.com")

    response = await client.post(
        "/api/v1/shift-types",
        json={
            "code": "BROKEN",
            "name_pl": "Zepsuty",
            "name_en": "Broken",
            "start_time": "08:00:00",
            "end_time": "16:00:00",
            "active_weekdays": 127,
            "default_required_staff": 5,
            "default_min_staff": 3,
            "default_max_staff": 4,
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["message_key"] == "shift_type.invalid_staff_levels"
