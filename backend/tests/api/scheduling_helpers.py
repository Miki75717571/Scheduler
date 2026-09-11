"""Shared setup helpers for the Phase 2 (scheduling core) API tests -
tests/api/test_periods.py, test_availability.py, test_shift_types.py,
test_rules.py all need a logged-in user and seeded shift types, so this
factors out what test_users.py/test_invitations.py leave duplicated (those
only need the plain user+login pair, not a shift-type fixture too).
"""

from datetime import time

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.shift_type import ShiftType
from app.models.user import EmploymentType, Role, User


async def create_user(
    db_session: AsyncSession,
    *,
    email: str,
    password: str = "password123",
    role: Role = Role.EMPLOYEE,
    employment_type: EmploymentType | None = None,
    full_name: str = "Test User",
) -> User:
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
        employment_type=employment_type,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def login(client: AsyncClient, email: str, password: str = "password123") -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return str(response.json()["access_token"])


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def create_shift_types(db_session: AsyncSession) -> dict[str, ShiftType]:
    """MORNING/EVENING on every day, MIDDAY on Sat+Sun only - mirrors the
    demo config in app/seed.py, kept in sync manually since both are just
    example data, not something either side derives from the other.
    """
    morning = ShiftType(
        code="MORNING",
        name_pl="Rano",
        name_en="Morning",
        start_time=time(7, 0),
        end_time=time(15, 0),
        active_weekdays=127,
        default_required_staff=2,
        default_min_staff=1,
        default_max_staff=3,
    )
    evening = ShiftType(
        code="EVENING",
        name_pl="Wieczor",
        name_en="Evening",
        start_time=time(15, 0),
        end_time=time(23, 0),
        active_weekdays=127,
        default_required_staff=2,
        default_min_staff=1,
        default_max_staff=3,
    )
    midday = ShiftType(
        code="MIDDAY",
        name_pl="Poludnie",
        name_en="Midday",
        start_time=time(11, 0),
        end_time=time(19, 0),
        active_weekdays=96,  # Sat (32) | Sun (64)
        default_required_staff=1,
        default_min_staff=1,
        default_max_staff=2,
    )
    db_session.add_all([morning, evening, midday])
    await db_session.commit()
    for shift_type in (morning, evening, midday):
        await db_session.refresh(shift_type)
    return {"MORNING": morning, "EVENING": evening, "MIDDAY": midday}
