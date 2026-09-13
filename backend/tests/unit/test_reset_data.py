from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import reset_data
from app.core.security import hash_password
from app.models.assignment import Assignment
from app.models.availability import Availability, AvailabilityStatus, AvailabilitySubmission
from app.models.employee_score import EmployeeScore
from app.models.invitation import Invitation
from app.models.rule import Rule, RulePhase, RuleScope, RuleSeverity, RuleType
from app.models.schedule_period import PeriodState, SchedulePeriod
from app.models.score_criterion import ScoreCriterion
from app.models.shift_slot import ShiftSlot
from app.models.shift_type import ShiftType
from app.models.user import Role, User

_PASSWORD_HASH = hash_password("password123")


async def test_reset_data_keeps_admins_and_real_config_but_wipes_everything_else(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # reset_data.run() does `async with SessionLocal() as db` - swap in a
    # trivial async context manager around this test's own db_session so the
    # deletes land in the same SAVEPOINT-backed transaction the fixture rolls
    # back afterward (see tests/conftest.py's db_session docstring).
    class _Ctx:
        async def __aenter__(self) -> AsyncSession:
            return db_session

        async def __aexit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(reset_data, "SessionLocal", lambda: _Ctx())

    admin = User(
        email="admin@example.com",
        password_hash=_PASSWORD_HASH,
        full_name="Admin",
        role=Role.ADMIN,
        is_active=True,
    )
    employee = User(
        email="emp@example.com",
        password_hash=_PASSWORD_HASH,
        full_name="Employee",
        role=Role.EMPLOYEE,
        is_active=True,
    )
    db_session.add_all([admin, employee])
    await db_session.flush()

    shift_type = ShiftType(
        code="MORNING",
        name_pl="Rano",
        name_en="Morning",
        start_time=datetime(2024, 1, 1, 8, 30).time(),
        end_time=datetime(2024, 1, 1, 14, 0).time(),
        active_weekdays=127,
        default_required_staff=1,
        default_min_staff=1,
        default_max_staff=1,
    )
    rule = Rule(
        code="min_15_availability",
        name_pl="x",
        name_en="x",
        type=RuleType.MIN_AVAILABILITY_COUNT,
        scope=RuleScope.GLOBAL,
        params={"n": 15},
        severity=RuleSeverity.HARD,
        phase=RulePhase.AVAILABILITY,
    )
    criterion = ScoreCriterion(
        code="SPEED", name_pl="x", name_en="x", weight=Decimal("1.0"), is_active=True
    )
    db_session.add_all([shift_type, rule, criterion])
    await db_session.flush()

    period = SchedulePeriod(year=2027, month=1, state=PeriodState.COLLECTING)
    db_session.add(period)
    await db_session.flush()

    slot = ShiftSlot(
        period_id=period.id,
        date=date(2027, 1, 4),
        shift_type_id=shift_type.id,
        required_staff=1,
        min_staff=1,
        max_staff=1,
    )
    db_session.add(slot)
    await db_session.flush()

    assignment = Assignment(shift_slot_id=slot.id, user_id=employee.id, created_by_user_id=admin.id)
    submission = AvailabilitySubmission(user_id=employee.id, period_id=period.id)
    db_session.add_all([assignment, submission])
    await db_session.flush()

    availability = Availability(
        submission_id=submission.id, shift_slot_id=slot.id, status=AvailabilityStatus.AVAILABLE
    )
    score = EmployeeScore(
        user_id=employee.id,
        criterion_id=criterion.id,
        value=4,
        effective_from=date(2027, 1, 1),
        set_by_user_id=admin.id,
    )
    invitation = Invitation(
        email="future@example.com",
        role=Role.EMPLOYEE,
        token_hash="hash",
        expires_at=datetime.now(UTC),
        created_by_user_id=admin.id,
    )
    db_session.add_all([availability, score, invitation])
    await db_session.commit()

    await reset_data.run()

    remaining_users = (await db_session.execute(select(User))).scalars().all()
    assert [u.email for u in remaining_users] == ["admin@example.com"]

    assert (await db_session.execute(select(SchedulePeriod))).scalars().all() == []
    assert (await db_session.execute(select(ShiftSlot))).scalars().all() == []
    assert (await db_session.execute(select(Assignment))).scalars().all() == []
    assert (await db_session.execute(select(AvailabilitySubmission))).scalars().all() == []
    assert (await db_session.execute(select(Availability))).scalars().all() == []
    assert (await db_session.execute(select(EmployeeScore))).scalars().all() == []
    assert (await db_session.execute(select(Invitation))).scalars().all() == []

    # Real config survives untouched.
    kept_shift_types = (await db_session.execute(select(ShiftType))).scalars().all()
    assert [s.code for s in kept_shift_types] == ["MORNING"]
    kept_rules = (await db_session.execute(select(Rule))).scalars().all()
    assert [r.code for r in kept_rules] == ["min_15_availability"]
    kept_criteria = (await db_session.execute(select(ScoreCriterion))).scalars().all()
    assert [c.code for c in kept_criteria] == ["SPEED"]
