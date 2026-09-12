"""API-level tests for the Phase 5 solver endpoints. The pure CP-SAT model
itself is covered exhaustively in tests/scheduling/test_cpsat_golden.py -
these tests exercise the plumbing around it: 202-then-poll, role
enforcement, and that regenerating a period preserves manager locks
end-to-end through the real DB layer (ARCHITECTURE.md ss3.6).
"""

import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability import Availability, AvailabilityStatus, AvailabilitySubmission
from app.models.user import Role
from tests.api.scheduling_helpers import auth_headers, create_shift_types, create_user, login
from tests.api.test_assignments import _make_generated_period, _shift_type_codes_by_id, _slots


async def _seed_availability(
    db_session: AsyncSession,
    *,
    period_id: str,
    user_id: uuid.UUID,
    slot_ids: list[str],
    status: AvailabilityStatus = AvailabilityStatus.AVAILABLE,
) -> None:
    submission = AvailabilitySubmission(user_id=user_id, period_id=uuid.UUID(period_id))
    db_session.add(submission)
    await db_session.flush()
    for slot_id in slot_ids:
        db_session.add(
            Availability(
                submission_id=submission.id, shift_slot_id=uuid.UUID(slot_id), status=status
            )
        )
    await db_session.commit()


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


async def test_employee_cannot_create_schedule_run(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _headers, period_id, _slots, _types = await _setup(
        client, db_session, manager_email="run-mgr-403@example.com", year=2031, month=1
    )
    employee = await create_user(db_session, email="run-emp-403@example.com", role=Role.EMPLOYEE)
    employee_headers = auth_headers(await login(client, employee.email))

    response = await client.post(
        f"/api/v1/periods/{period_id}/schedule-runs", json={}, headers=employee_headers
    )
    assert response.status_code == 403


async def test_schedule_run_cannot_be_created_before_locked(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_shift_types(db_session)
    await create_user(db_session, email="run-draft-mgr@example.com", role=Role.MANAGER)
    manager_headers = auth_headers(await login(client, "run-draft-mgr@example.com"))
    period_id = (
        await client.post(
            "/api/v1/periods", json={"year": 2031, "month": 2}, headers=manager_headers
        )
    ).json()["id"]

    response = await client.post(
        f"/api/v1/periods/{period_id}/schedule-runs", json={}, headers=manager_headers
    )
    assert response.status_code == 409
    assert response.json()["detail"]["message_key"] == "schedule_run.period_not_ready"


async def test_manager_creates_a_run_and_it_completes_in_the_background(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    manager_headers, period_id, slots, type_by_id = await _setup(
        client, db_session, manager_email="run-mgr-happy@example.com", year=2031, month=3
    )
    employee = await create_user(db_session, email="run-emp-happy@example.com", role=Role.EMPLOYEE)
    morning_slots = [s["id"] for s in slots if type_by_id[s["shift_type_id"]] == "MORNING"]
    await _seed_availability(
        db_session, period_id=period_id, user_id=employee.id, slot_ids=morning_slots
    )

    create_response = await client.post(
        f"/api/v1/periods/{period_id}/schedule-runs", json={}, headers=manager_headers
    )
    assert create_response.status_code == 202, create_response.text
    run_body = create_response.json()
    assert run_body["status"] == "PENDING"
    assert run_body["algorithm_version"]
    run_id = run_body["id"]

    # ASGITransport awaits Starlette's background tasks as part of the same
    # request/response cycle in-process, so by the time the POST above has
    # returned the run has already finished - no polling loop needed here.
    get_response = await client.get(f"/api/v1/schedule-runs/{run_id}", headers=manager_headers)
    assert get_response.status_code == 200
    finished = get_response.json()
    assert finished["status"] == "SUCCESS", finished
    assert finished["solver_status"] in ("OPTIMAL", "FEASIBLE")
    assert finished["stats"]["total_slots"] == len(slots)
    assert finished["diagnostics"] is not None

    list_response = await client.get(
        f"/api/v1/periods/{period_id}/schedule-runs", headers=manager_headers
    )
    assert [r["id"] for r in list_response.json()] == [run_id]

    assignments_response = await client.get(
        f"/api/v1/periods/{period_id}/assignments", headers=manager_headers
    )
    assigned_slot_ids = {a["shift_slot_id"] for a in assignments_response.json()}
    assert assigned_slot_ids, "expected at least one MORNING assignment for the available employee"
    assert assigned_slot_ids <= set(morning_slots)


async def test_regenerating_preserves_a_locked_assignment(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    manager_headers, period_id, slots, _types = await _setup(
        client, db_session, manager_email="run-mgr-lock@example.com", year=2031, month=4
    )
    kept = await create_user(db_session, email="run-emp-kept@example.com", role=Role.EMPLOYEE)
    other = await create_user(db_session, email="run-emp-other@example.com", role=Role.EMPLOYEE)

    locked_slot = slots[0]
    all_slot_ids = [s["id"] for s in slots]
    await _seed_availability(
        db_session, period_id=period_id, user_id=other.id, slot_ids=all_slot_ids
    )

    # Manager manually assigns and locks `kept` into a slot BEFORE ever
    # running the solver - a manual pin the solver must not touch.
    create_assignment = await client.post(
        f"/api/v1/periods/{period_id}/assignments",
        json={"shift_slot_id": locked_slot["id"], "user_id": str(kept.id)},
        headers=manager_headers,
    )
    assert create_assignment.status_code == 201, create_assignment.text
    assignment_id = create_assignment.json()["assignment"]["id"]
    lock_response = await client.patch(
        f"/api/v1/periods/{period_id}/assignments/{assignment_id}/lock",
        json={"is_locked": True},
        headers=manager_headers,
    )
    assert lock_response.status_code == 200

    run_response = await client.post(
        f"/api/v1/periods/{period_id}/schedule-runs", json={}, headers=manager_headers
    )
    assert run_response.status_code == 202

    assignments_response = await client.get(
        f"/api/v1/periods/{period_id}/assignments", headers=manager_headers
    )
    assignments = assignments_response.json()
    kept_assignment = next(a for a in assignments if a["id"] == assignment_id)
    assert kept_assignment["shift_slot_id"] == locked_slot["id"]
    assert kept_assignment["user_id"] == str(kept.id)
    assert kept_assignment["is_locked"] is True


async def test_solver_weights_are_admin_only_and_roundtrip(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="run-mgr-weights@example.com", role=Role.MANAGER)
    await create_user(db_session, email="run-admin-weights@example.com", role=Role.ADMIN)
    manager_headers = auth_headers(await login(client, "run-mgr-weights@example.com"))
    admin_headers = auth_headers(await login(client, "run-admin-weights@example.com"))

    forbidden = await client.get("/api/v1/solver/weights", headers=manager_headers)
    assert forbidden.status_code == 403

    get_response = await client.get("/api/v1/solver/weights", headers=admin_headers)
    assert get_response.status_code == 200
    defaults = get_response.json()
    assert defaults["understaffing"] == 10000

    update_response = await client.put(
        "/api/v1/solver/weights",
        json={
            "understaffing": 9000,
            "contract_min_shortfall": 900,
            "denied_preference": 15,
            "fairness_spread": 25,
            "unpopular_shift_spread": 20,
            "score_weight": 8,
            "preference_debt": 12,
        },
        headers=admin_headers,
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["understaffing"] == 9000
    assert updated["updated_by_user_id"]
