from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rule import Rule, RulePhase, RuleScope, RuleSeverity, RuleType
from app.models.user import Role
from tests.api.scheduling_helpers import auth_headers, create_shift_types, create_user, login


async def _make_generated_period(
    client: AsyncClient, manager_headers: dict[str, str], year: int, month: int
) -> str:
    period_id = (
        await client.post(
            "/api/v1/periods", json={"year": year, "month": month}, headers=manager_headers
        )
    ).json()["id"]
    for target in ("COLLECTING", "LOCKED", "GENERATED"):
        response = await client.patch(
            f"/api/v1/periods/{period_id}/state", json={"state": target}, headers=manager_headers
        )
        assert response.status_code == 200, response.text
    return str(period_id)


async def _shift_type_codes_by_id(client: AsyncClient, headers: dict[str, str]) -> dict[str, str]:
    response = await client.get("/api/v1/shift-types", headers=headers)
    return {st["id"]: st["code"] for st in response.json()}


async def _slots(
    client: AsyncClient, headers: dict[str, str], period_id: str
) -> list[dict[str, Any]]:
    response = await client.get(f"/api/v1/periods/{period_id}/slots", headers=headers)
    return list(response.json())


def _find_slot(
    slots: list[dict[str, Any]], type_by_id: dict[str, str], date_str: str, code: str
) -> dict[str, Any]:
    for slot in slots:
        if slot["date"] == date_str and type_by_id[slot["shift_type_id"]] == code:
            return slot
    raise AssertionError(f"no slot found for {date_str} {code}")


async def _setup(
    client: AsyncClient, db_session: AsyncSession, *, manager_email: str, year: int, month: int
) -> tuple[dict[str, str], str, list[dict[str, Any]], dict[str, str]]:
    await create_shift_types(db_session)
    await create_user(db_session, email=manager_email, role=Role.MANAGER)
    manager_headers = auth_headers(await login(client, manager_email))
    period_id = await _make_generated_period(client, manager_headers, year, month)
    slots = await _slots(client, manager_headers, period_id)
    type_by_id = await _shift_type_codes_by_id(client, manager_headers)
    return manager_headers, period_id, slots, type_by_id


# --- CRUD lifecycle --------------------------------------------------------


async def test_manager_can_create_move_lock_and_remove_an_assignment(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    manager_headers, period_id, slots, type_by_id = await _setup(
        client, db_session, manager_email="mgr-crud@example.com", year=2030, month=1
    )
    slot_a = _find_slot(slots, type_by_id, "2030-01-05", "MORNING")
    slot_b = _find_slot(slots, type_by_id, "2030-01-06", "MORNING")
    employee = await create_user(db_session, email="crud-emp@example.com", role=Role.EMPLOYEE)

    create_response = await client.post(
        f"/api/v1/periods/{period_id}/assignments",
        json={"shift_slot_id": slot_a["id"], "user_id": str(employee.id)},
        headers=manager_headers,
    )
    assert create_response.status_code == 201, create_response.text
    body = create_response.json()
    assignment = body["assignment"]
    assert assignment["shift_slot_id"] == slot_a["id"]
    assert assignment["source"] == "MANUAL"
    assert assignment["is_locked"] is False
    assignment_id = assignment["id"]

    move_response = await client.patch(
        f"/api/v1/periods/{period_id}/assignments/{assignment_id}/move",
        json={"shift_slot_id": slot_b["id"]},
        headers=manager_headers,
    )
    assert move_response.status_code == 200, move_response.text
    assert move_response.json()["assignment"]["shift_slot_id"] == slot_b["id"]

    lock_response = await client.patch(
        f"/api/v1/periods/{period_id}/assignments/{assignment_id}/lock",
        json={"is_locked": True},
        headers=manager_headers,
    )
    assert lock_response.status_code == 200
    assert lock_response.json()["is_locked"] is True

    list_response = await client.get(
        f"/api/v1/periods/{period_id}/assignments", headers=manager_headers
    )
    assert list_response.status_code == 200
    assert [a["id"] for a in list_response.json()] == [assignment_id]

    remove_response = await client.delete(
        f"/api/v1/periods/{period_id}/assignments/{assignment_id}", headers=manager_headers
    )
    assert remove_response.status_code == 200
    assert remove_response.json()["assignment"] is None

    final_list = await client.get(
        f"/api/v1/periods/{period_id}/assignments", headers=manager_headers
    )
    assert final_list.json() == []

    audit_response = await client.get(
        f"/api/v1/periods/{period_id}/audit-log", headers=manager_headers
    )
    assert audit_response.status_code == 200
    actions = [e["action"] for e in audit_response.json()]
    assert actions.count("assignment.create") == 1
    assert actions.count("assignment.move") == 1
    assert actions.count("assignment.lock") == 1
    assert actions.count("assignment.remove") == 1


async def test_employee_cannot_mutate_assignments(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    manager_headers, period_id, slots, type_by_id = await _setup(
        client, db_session, manager_email="mgr-403@example.com", year=2030, month=2
    )
    slot = _find_slot(slots, type_by_id, "2030-02-05", "MORNING")
    employee = await create_user(db_session, email="emp-403@example.com", role=Role.EMPLOYEE)
    employee_headers = auth_headers(await login(client, "emp-403@example.com"))

    response = await client.post(
        f"/api/v1/periods/{period_id}/assignments",
        json={"shift_slot_id": slot["id"], "user_id": str(employee.id)},
        headers=employee_headers,
    )
    assert response.status_code == 403


async def test_creating_duplicate_assignment_conflicts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    manager_headers, period_id, slots, type_by_id = await _setup(
        client, db_session, manager_email="mgr-dup@example.com", year=2030, month=3
    )
    slot = _find_slot(slots, type_by_id, "2030-03-05", "MORNING")
    employee = await create_user(db_session, email="dup-emp@example.com", role=Role.EMPLOYEE)

    payload = {"shift_slot_id": slot["id"], "user_id": str(employee.id)}
    first = await client.post(
        f"/api/v1/periods/{period_id}/assignments", json=payload, headers=manager_headers
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/periods/{period_id}/assignments", json=payload, headers=manager_headers
    )
    assert second.status_code == 409
    assert second.json()["detail"]["message_key"] == "assignment.already_exists"


async def test_assigning_to_a_closed_slot_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    manager_headers, period_id, slots, type_by_id = await _setup(
        client, db_session, manager_email="mgr-closed@example.com", year=2030, month=4
    )
    slot = _find_slot(slots, type_by_id, "2030-04-05", "MORNING")
    await client.patch(
        f"/api/v1/periods/{period_id}/slots/{slot['id']}",
        json={"is_closed": True},
        headers=manager_headers,
    )
    employee = await create_user(db_session, email="closed-emp@example.com", role=Role.EMPLOYEE)

    response = await client.post(
        f"/api/v1/periods/{period_id}/assignments",
        json={"shift_slot_id": slot["id"], "user_id": str(employee.id)},
        headers=manager_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"]["message_key"] == "assignment.slot_closed"


async def test_bulk_add_operations_return_assignments_and_violations(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    manager_headers, period_id, slots, type_by_id = await _setup(
        client, db_session, manager_email="mgr-bulk@example.com", year=2030, month=5
    )
    slot_a = _find_slot(slots, type_by_id, "2030-05-05", "MORNING")
    slot_b = _find_slot(slots, type_by_id, "2030-05-06", "MORNING")
    employee1 = await create_user(db_session, email="bulk1@example.com", role=Role.EMPLOYEE)
    employee2 = await create_user(db_session, email="bulk2@example.com", role=Role.EMPLOYEE)

    response = await client.post(
        f"/api/v1/periods/{period_id}/assignments/bulk",
        json={
            "operations": [
                {"op": "add", "shift_slot_id": slot_a["id"], "user_id": str(employee1.id)},
                {"op": "add", "shift_slot_id": slot_b["id"], "user_id": str(employee2.id)},
            ]
        },
        headers=manager_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["assignments"]) == 2
    assert isinstance(body["violations"], list)


async def test_bulk_operation_missing_required_field_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    manager_headers, period_id, _slots, _types = await _setup(
        client, db_session, manager_email="mgr-bulk-bad@example.com", year=2030, month=6
    )

    response = await client.post(
        f"/api/v1/periods/{period_id}/assignments/bulk",
        json={"operations": [{"op": "move"}]},
        headers=manager_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"]["message_key"] == "assignment.invalid_bulk_operation"


# --- violations -------------------------------------------------------------


async def test_understaffed_slot_produces_error_and_warning(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    manager_headers, period_id, slots, type_by_id = await _setup(
        client, db_session, manager_email="mgr-under@example.com", year=2030, month=7
    )
    # default_min_staff=1, default_required_staff=2 for MORNING (see create_shift_types)
    warning_slot = _find_slot(slots, type_by_id, "2030-07-05", "MORNING")
    error_slot = _find_slot(slots, type_by_id, "2030-07-06", "MORNING")
    employee = await create_user(db_session, email="under-emp@example.com", role=Role.EMPLOYEE)

    await client.post(
        f"/api/v1/periods/{period_id}/assignments",
        json={"shift_slot_id": warning_slot["id"], "user_id": str(employee.id)},
        headers=manager_headers,
    )
    # error_slot is left with 0 assignments: below min_staff=1 -> ERROR.

    response = await client.get(f"/api/v1/periods/{period_id}/violations", headers=manager_headers)
    assert response.status_code == 200
    violations = response.json()

    warning = next(
        v
        for v in violations
        if v["shift_slot_id"] == warning_slot["id"]
        and v["message_key"] == "schedule.understaffed_below_required"
    )
    assert warning["severity"] == "WARNING"

    error = next(
        v
        for v in violations
        if v["shift_slot_id"] == error_slot["id"]
        and v["message_key"] == "schedule.understaffed_below_minimum"
    )
    assert error["severity"] == "ERROR"


async def test_double_booking_is_flagged_by_one_shift_per_day_rule(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    manager_headers, period_id, slots, type_by_id = await _setup(
        client, db_session, manager_email="mgr-double@example.com", year=2030, month=8
    )
    morning = _find_slot(slots, type_by_id, "2030-08-05", "MORNING")
    evening = _find_slot(slots, type_by_id, "2030-08-05", "EVENING")
    employee = await create_user(db_session, email="double-emp@example.com", role=Role.EMPLOYEE)

    db_session.add(
        Rule(
            code="one_shift_per_day",
            name_pl="Jedna zmiana dziennie",
            name_en="One shift per day",
            type=RuleType.ONE_SHIFT_PER_DAY,
            scope=RuleScope.GLOBAL,
            params={},
            severity=RuleSeverity.HARD,
            phase=RulePhase.SCHEDULE,
            is_active=True,
        )
    )
    await db_session.commit()

    for slot in (morning, evening):
        response = await client.post(
            f"/api/v1/periods/{period_id}/assignments",
            json={"shift_slot_id": slot["id"], "user_id": str(employee.id)},
            headers=manager_headers,
        )
        assert response.status_code == 201

    violations = (
        await client.get(f"/api/v1/periods/{period_id}/violations", headers=manager_headers)
    ).json()
    one_shift_violations = [v for v in violations if v["rule_code"] == "one_shift_per_day"]
    assert len(one_shift_violations) == 1
    assert one_shift_violations[0]["severity"] == "ERROR"


async def test_assigning_despite_unavailable_is_a_warning(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    manager_headers, period_id, slots, type_by_id = await _setup(
        client, db_session, manager_email="mgr-unavail@example.com", year=2030, month=9
    )
    slot = _find_slot(slots, type_by_id, "2030-09-05", "MORNING")
    employee = await create_user(db_session, email="unavail-emp@example.com", role=Role.EMPLOYEE)

    response = await client.post(
        f"/api/v1/periods/{period_id}/assignments",
        json={"shift_slot_id": slot["id"], "user_id": str(employee.id)},
        headers=manager_headers,
    )
    assert response.status_code == 201
    violations = response.json()["violations"]

    match = next(
        v
        for v in violations
        if v["message_key"] == "schedule.assigned_despite_unavailable"
        and v["user_id"] == str(employee.id)
        and v["shift_slot_id"] == slot["id"]
    )
    assert match["severity"] == "WARNING"


async def test_available_employees_excludes_a_hard_rule_conflict(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="mgr-avail@example.com", role=Role.MANAGER)
    manager_headers = auth_headers(await login(client, "mgr-avail@example.com"))
    employee = await create_user(db_session, email="avail-emp@example.com", role=Role.EMPLOYEE)

    # Availability can only be written while COLLECTING, so declare it before
    # advancing the period on to LOCKED/GENERATED.
    period_id = (
        await client.post(
            "/api/v1/periods", json={"year": 2030, "month": 10}, headers=manager_headers
        )
    ).json()["id"]
    await client.patch(
        f"/api/v1/periods/{period_id}/state", json={"state": "COLLECTING"}, headers=manager_headers
    )
    slots = await _slots(client, manager_headers, period_id)
    type_by_id = await _shift_type_codes_by_id(client, manager_headers)
    morning = _find_slot(slots, type_by_id, "2030-10-05", "MORNING")
    evening = _find_slot(slots, type_by_id, "2030-10-05", "EVENING")

    employee_headers = auth_headers(await login(client, "avail-emp@example.com"))
    await client.put(
        f"/api/v1/periods/{period_id}/availability/{employee.id}",
        json={
            "entries": [
                {"shift_slot_id": morning["id"], "status": "AVAILABLE"},
                {"shift_slot_id": evening["id"], "status": "PREFERRED"},
            ]
        },
        headers=employee_headers,
    )

    for target in ("LOCKED", "GENERATED"):
        await client.patch(
            f"/api/v1/periods/{period_id}/state", json={"state": target}, headers=manager_headers
        )

    db_session.add(
        Rule(
            code="one_shift_per_day_2",
            name_pl="Jedna zmiana dziennie",
            name_en="One shift per day",
            type=RuleType.ONE_SHIFT_PER_DAY,
            scope=RuleScope.GLOBAL,
            params={},
            severity=RuleSeverity.HARD,
            phase=RulePhase.SCHEDULE,
            is_active=True,
        )
    )
    await db_session.commit()

    # Before any assignment, they're a valid candidate for the evening slot.
    before = await client.get(
        f"/api/v1/periods/{period_id}/slots/{evening['id']}/available-employees",
        headers=manager_headers,
    )
    assert before.status_code == 200
    assert any(c["user_id"] == str(employee.id) for c in before.json())

    # Once assigned to the morning slot, they're excluded from the evening
    # slot's candidates - assigning them there would violate ONE_SHIFT_PER_DAY.
    await client.post(
        f"/api/v1/periods/{period_id}/assignments",
        json={"shift_slot_id": morning["id"], "user_id": str(employee.id)},
        headers=manager_headers,
    )

    after = await client.get(
        f"/api/v1/periods/{period_id}/slots/{evening['id']}/available-employees",
        headers=manager_headers,
    )
    assert after.status_code == 200
    assert all(c["user_id"] != str(employee.id) for c in after.json())


# --- publish gating ----------------------------------------------------


async def test_publish_is_blocked_by_error_violations_unless_overridden(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    manager_headers, period_id, _slots, _types = await _setup(
        client, db_session, manager_email="mgr-publish@example.com", year=2030, month=11
    )
    # No assignments at all: every slot is below min_staff -> ERROR everywhere.

    blocked = await client.patch(
        f"/api/v1/periods/{period_id}/state",
        json={"state": "PUBLISHED"},
        headers=manager_headers,
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["message_key"] == "period.publish_blocked_by_errors"
    assert blocked.json()["detail"]["params"]["error_count"] > 0

    overridden = await client.patch(
        f"/api/v1/periods/{period_id}/state",
        json={"state": "PUBLISHED", "override_violations": True},
        headers=manager_headers,
    )
    assert overridden.status_code == 200
    assert overridden.json()["state"] == "PUBLISHED"

    audit_response = await client.get(
        f"/api/v1/periods/{period_id}/audit-log", headers=manager_headers
    )
    actions = [e["action"] for e in audit_response.json()]
    assert "period.publish_override" in actions


# --- employee read access ------------------------------------------------


async def test_employee_cannot_read_assignments_before_publish(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    manager_headers, period_id, slots, type_by_id = await _setup(
        client, db_session, manager_email="mgr-unpub@example.com", year=2030, month=12
    )
    slot = _find_slot(slots, type_by_id, "2030-12-05", "MORNING")
    employee = await create_user(db_session, email="unpub-emp@example.com", role=Role.EMPLOYEE)
    await client.post(
        f"/api/v1/periods/{period_id}/assignments",
        json={"shift_slot_id": slot["id"], "user_id": str(employee.id)},
        headers=manager_headers,
    )
    employee_headers = auth_headers(await login(client, "unpub-emp@example.com"))

    response = await client.get(
        f"/api/v1/periods/{period_id}/assignments", headers=employee_headers
    )
    assert response.status_code == 403


async def test_employee_sees_own_and_shared_shift_assignments_once_published(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    manager_headers, period_id, slots, type_by_id = await _setup(
        client, db_session, manager_email="mgr-pub@example.com", year=2031, month=1
    )
    shared_slot = _find_slot(slots, type_by_id, "2031-01-05", "MORNING")
    other_slot = _find_slot(slots, type_by_id, "2031-01-06", "MORNING")

    employee1 = await create_user(db_session, email="pub-emp1@example.com", role=Role.EMPLOYEE)
    employee2 = await create_user(db_session, email="pub-emp2@example.com", role=Role.EMPLOYEE)
    employee3 = await create_user(db_session, email="pub-emp3@example.com", role=Role.EMPLOYEE)

    for user in (employee1, employee2):
        await client.post(
            f"/api/v1/periods/{period_id}/assignments",
            json={"shift_slot_id": shared_slot["id"], "user_id": str(user.id)},
            headers=manager_headers,
        )
    await client.post(
        f"/api/v1/periods/{period_id}/assignments",
        json={"shift_slot_id": other_slot["id"], "user_id": str(employee3.id)},
        headers=manager_headers,
    )

    publish = await client.patch(
        f"/api/v1/periods/{period_id}/state",
        json={"state": "PUBLISHED", "override_violations": True},
        headers=manager_headers,
    )
    assert publish.status_code == 200

    employee1_headers = auth_headers(await login(client, "pub-emp1@example.com"))
    response = await client.get(
        f"/api/v1/periods/{period_id}/assignments", headers=employee1_headers
    )
    assert response.status_code == 200
    seen_user_ids = {a["user_id"] for a in response.json()}
    assert seen_user_ids == {str(employee1.id), str(employee2.id)}


async def test_employee_cannot_read_audit_log_or_violations(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    manager_headers, period_id, _slots, _types = await _setup(
        client, db_session, manager_email="mgr-auditor@example.com", year=2031, month=2
    )
    await create_user(db_session, email="auditor-emp@example.com", role=Role.EMPLOYEE)
    employee_headers = auth_headers(await login(client, "auditor-emp@example.com"))

    audit_response = await client.get(
        f"/api/v1/periods/{period_id}/audit-log", headers=employee_headers
    )
    assert audit_response.status_code == 403

    violations_response = await client.get(
        f"/api/v1/periods/{period_id}/violations", headers=employee_headers
    )
    assert violations_response.status_code == 403
