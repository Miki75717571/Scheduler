from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rule import Rule, RulePhase, RuleScope, RuleSeverity, RuleType
from app.models.user import Role
from tests.api.scheduling_helpers import auth_headers, create_shift_types, create_user, login


async def _make_collecting_period(
    client: AsyncClient, manager_headers: dict[str, str], year: int, month: int
) -> str:
    period_id = (
        await client.post(
            "/api/v1/periods", json={"year": year, "month": month}, headers=manager_headers
        )
    ).json()["id"]
    await client.patch(
        f"/api/v1/periods/{period_id}/state", json={"state": "COLLECTING"}, headers=manager_headers
    )
    return str(period_id)


async def _first_slot_id(client: AsyncClient, headers: dict[str, str], period_id: str) -> str:
    slots = (await client.get(f"/api/v1/periods/{period_id}/slots", headers=headers)).json()
    return str(slots[0]["id"])


async def test_employee_can_read_own_availability(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="mgr1@example.com", role=Role.MANAGER)
    manager_token = await login(client, "mgr1@example.com")
    period_id = await _make_collecting_period(client, auth_headers(manager_token), 2028, 1)

    employee = await create_user(db_session, email="alice2@example.com", role=Role.EMPLOYEE)
    token = await login(client, "alice2@example.com")

    response = await client.get(
        f"/api/v1/periods/{period_id}/availability/{employee.id}", headers=auth_headers(token)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["submission"]["user_id"] == str(employee.id)
    assert body["entries"] == []


async def test_employee_gets_403_reading_someone_elses_availability(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="mgr2@example.com", role=Role.MANAGER)
    manager_token = await login(client, "mgr2@example.com")
    period_id = await _make_collecting_period(client, auth_headers(manager_token), 2028, 2)

    target = await create_user(
        db_session, email="bob2@example.com", role=Role.EMPLOYEE, full_name="Bob"
    )
    await create_user(db_session, email="carl2@example.com", role=Role.EMPLOYEE, full_name="Carl")
    token = await login(client, "carl2@example.com")

    response = await client.get(
        f"/api/v1/periods/{period_id}/availability/{target.id}", headers=auth_headers(token)
    )

    assert response.status_code == 403


async def test_manager_can_read_any_employees_availability(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    manager = await create_user(db_session, email="mgr3@example.com", role=Role.MANAGER)
    manager_token = await login(client, "mgr3@example.com")
    period_id = await _make_collecting_period(client, auth_headers(manager_token), 2028, 3)

    target = await create_user(db_session, email="dave2@example.com", role=Role.EMPLOYEE)

    response = await client.get(
        f"/api/v1/periods/{period_id}/availability/{target.id}", headers=auth_headers(manager_token)
    )

    assert response.status_code == 200
    assert manager.role == Role.MANAGER  # sanity


async def test_employee_can_write_and_read_back_own_availability(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="mgr4@example.com", role=Role.MANAGER)
    manager_token = await login(client, "mgr4@example.com")
    period_id = await _make_collecting_period(client, auth_headers(manager_token), 2028, 4)

    employee = await create_user(db_session, email="erin2@example.com", role=Role.EMPLOYEE)
    token = await login(client, "erin2@example.com")
    headers = auth_headers(token)
    slot_id = await _first_slot_id(client, headers, period_id)

    response = await client.put(
        f"/api/v1/periods/{period_id}/availability/{employee.id}",
        json={"entries": [{"shift_slot_id": slot_id, "status": "PREFERRED"}]},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["submission"]["status"] == "DRAFT"
    assert body["entries"] == [{"shift_slot_id": slot_id, "status": "PREFERRED", "note": None}]


async def test_employee_cannot_write_another_employees_availability(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="mgr5@example.com", role=Role.MANAGER)
    manager_token = await login(client, "mgr5@example.com")
    period_id = await _make_collecting_period(client, auth_headers(manager_token), 2028, 5)

    target = await create_user(db_session, email="frank2@example.com", role=Role.EMPLOYEE)
    await create_user(db_session, email="gina2@example.com", role=Role.EMPLOYEE, full_name="Gina")
    token = await login(client, "gina2@example.com")
    headers = auth_headers(token)
    slot_id = await _first_slot_id(client, headers, period_id)

    response = await client.put(
        f"/api/v1/periods/{period_id}/availability/{target.id}",
        json={"entries": [{"shift_slot_id": slot_id, "status": "AVAILABLE"}]},
        headers=headers,
    )

    assert response.status_code == 403


async def test_writing_availability_before_collecting_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="mgr6@example.com", role=Role.MANAGER)
    manager_token = await login(client, "mgr6@example.com")
    manager_headers = auth_headers(manager_token)
    period_id = (
        await client.post(
            "/api/v1/periods", json={"year": 2028, "month": 6}, headers=manager_headers
        )
    ).json()["id"]  # still DRAFT

    employee = await create_user(db_session, email="hank2@example.com", role=Role.EMPLOYEE)
    token = await login(client, "hank2@example.com")
    headers = auth_headers(token)
    slot_id = await _first_slot_id(client, headers, period_id)

    response = await client.put(
        f"/api/v1/periods/{period_id}/availability/{employee.id}",
        json={"entries": [{"shift_slot_id": slot_id, "status": "AVAILABLE"}]},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["message_key"] == "availability.period_not_editable"


async def test_editing_after_locked_is_rejected_until_manager_reopens(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="mgr7@example.com", role=Role.MANAGER)
    manager_token = await login(client, "mgr7@example.com")
    manager_headers = auth_headers(manager_token)
    period_id = await _make_collecting_period(client, manager_headers, 2028, 7)
    await client.patch(
        f"/api/v1/periods/{period_id}/state", json={"state": "LOCKED"}, headers=manager_headers
    )

    employee = await create_user(db_session, email="ivy2@example.com", role=Role.EMPLOYEE)
    token = await login(client, "ivy2@example.com")
    headers = auth_headers(token)
    slot_id = await _first_slot_id(client, headers, period_id)

    blocked = await client.put(
        f"/api/v1/periods/{period_id}/availability/{employee.id}",
        json={"entries": [{"shift_slot_id": slot_id, "status": "AVAILABLE"}]},
        headers=headers,
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["message_key"] == "availability.period_not_editable"

    reopen_response = await client.post(
        f"/api/v1/periods/{period_id}/availability/{employee.id}/reopen", headers=manager_headers
    )
    assert reopen_response.status_code == 200
    assert reopen_response.json()["reopened_by_manager"] is True

    allowed = await client.put(
        f"/api/v1/periods/{period_id}/availability/{employee.id}",
        json={"entries": [{"shift_slot_id": slot_id, "status": "AVAILABLE"}]},
        headers=headers,
    )
    assert allowed.status_code == 200

    revoke_response = await client.delete(
        f"/api/v1/periods/{period_id}/availability/{employee.id}/reopen", headers=manager_headers
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["reopened_by_manager"] is False

    blocked_again = await client.put(
        f"/api/v1/periods/{period_id}/availability/{employee.id}",
        json={"entries": [{"shift_slot_id": slot_id, "status": "PREFERRED"}]},
        headers=headers,
    )
    assert blocked_again.status_code == 409


async def test_employee_cannot_reopen_their_own_availability(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="mgr8@example.com", role=Role.MANAGER)
    manager_token = await login(client, "mgr8@example.com")
    period_id = await _make_collecting_period(client, auth_headers(manager_token), 2028, 8)

    employee = await create_user(db_session, email="jill2@example.com", role=Role.EMPLOYEE)
    token = await login(client, "jill2@example.com")

    response = await client.post(
        f"/api/v1/periods/{period_id}/availability/{employee.id}/reopen",
        headers=auth_headers(token),
    )

    assert response.status_code == 403


async def test_submit_is_blocked_by_a_failing_hard_rule(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="mgr9@example.com", role=Role.MANAGER)
    manager_token = await login(client, "mgr9@example.com")
    period_id = await _make_collecting_period(client, auth_headers(manager_token), 2028, 9)

    rule = Rule(
        code="min_2_shifts",
        name_pl="Minimum 2 zmiany",
        name_en="Minimum 2 shifts",
        type=RuleType.MIN_AVAILABILITY_COUNT,
        scope=RuleScope.GLOBAL,
        params={"n": 2},
        severity=RuleSeverity.HARD,
        phase=RulePhase.AVAILABILITY,
        is_active=True,
    )
    db_session.add(rule)
    await db_session.commit()

    employee = await create_user(db_session, email="kyle2@example.com", role=Role.EMPLOYEE)
    token = await login(client, "kyle2@example.com")
    headers = auth_headers(token)
    slot_id = await _first_slot_id(client, headers, period_id)

    await client.put(
        f"/api/v1/periods/{period_id}/availability/{employee.id}",
        json={"entries": [{"shift_slot_id": slot_id, "status": "AVAILABLE"}]},
        headers=headers,
    )

    submit_response = await client.post(
        f"/api/v1/periods/{period_id}/availability/{employee.id}/submit", headers=headers
    )

    assert submit_response.status_code == 422
    assert submit_response.json()["detail"]["message_key"] == "availability.hard_rules_failed"

    validate_response = await client.get(
        f"/api/v1/periods/{period_id}/availability/{employee.id}/validate", headers=headers
    )
    assert validate_response.status_code == 200
    results = validate_response.json()
    assert results[0]["rule_code"] == "min_2_shifts"
    assert results[0]["passed"] is False
    assert results[0]["message_key"] == "rules.MIN_AVAILABILITY_COUNT"
    assert results[0]["message_params"] == {"required": 2, "actual": 1}


async def test_submit_succeeds_once_hard_rules_pass(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="mgr10@example.com", role=Role.MANAGER)
    manager_token = await login(client, "mgr10@example.com")
    manager_headers = auth_headers(manager_token)
    period_id = await _make_collecting_period(client, manager_headers, 2028, 10)

    employee = await create_user(db_session, email="lena2@example.com", role=Role.EMPLOYEE)
    token = await login(client, "lena2@example.com")
    headers = auth_headers(token)

    slots = (await client.get(f"/api/v1/periods/{period_id}/slots", headers=headers)).json()
    entries = [{"shift_slot_id": s["id"], "status": "AVAILABLE"} for s in slots[:3]]
    await client.put(
        f"/api/v1/periods/{period_id}/availability/{employee.id}",
        json={"entries": entries},
        headers=headers,
    )

    response = await client.post(
        f"/api/v1/periods/{period_id}/availability/{employee.id}/submit", headers=headers
    )

    assert response.status_code == 200
    assert response.json()["submission"]["status"] == "SUBMITTED"


async def test_setting_a_slot_back_to_unavailable_removes_it(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="mgr11@example.com", role=Role.MANAGER)
    manager_token = await login(client, "mgr11@example.com")
    period_id = await _make_collecting_period(client, auth_headers(manager_token), 2028, 11)

    employee = await create_user(db_session, email="mike2@example.com", role=Role.EMPLOYEE)
    token = await login(client, "mike2@example.com")
    headers = auth_headers(token)
    slot_id = await _first_slot_id(client, headers, period_id)

    await client.put(
        f"/api/v1/periods/{period_id}/availability/{employee.id}",
        json={"entries": [{"shift_slot_id": slot_id, "status": "AVAILABLE"}]},
        headers=headers,
    )
    response = await client.put(
        f"/api/v1/periods/{period_id}/availability/{employee.id}",
        json={"entries": [{"shift_slot_id": slot_id, "status": "UNAVAILABLE"}]},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["entries"] == []


async def test_employee_cannot_view_submission_tracker(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="mgr12@example.com", role=Role.MANAGER)
    manager_token = await login(client, "mgr12@example.com")
    period_id = await _make_collecting_period(client, auth_headers(manager_token), 2028, 12)

    await create_user(db_session, email="nora2@example.com", role=Role.EMPLOYEE)
    token = await login(client, "nora2@example.com")

    response = await client.get(
        f"/api/v1/periods/{period_id}/availability/tracker", headers=auth_headers(token)
    )

    assert response.status_code == 403
