"""Demo data bootstrap.

Phase 1: the first ADMIN user, from environment variables, if none exists yet.
Phase 2 adds: the three demo ShiftTypes (MORNING/EVENING every day, MIDDAY
weekends only), the two demo availability rules from CLAUDE.md ("minimum 7
declared shifts", "at least 1 Friday evening"), ~18 employees with varied
employment types, and a demo SchedulePeriod for next month with a full
month of plausible availability already filled in (most employees
submitted, a few left in DRAFT or NOT_STARTED so the manager's submission
tracker has something to show).

Idempotent: re-running `uv run python -m app.seed` skips anything that
already exists (matched by code/email/year+month) rather than duplicating it
or crashing.

Phase 3 adds: the six SCHEDULE-phase rules (ARCHITECTURE.md ss3.5's defaults)
and a second demo period - the CURRENT month, advanced to GENERATED with a
handful of manual assignments - deliberately containing one of each
violation CLAUDE.md's Phase 3 brief calls out: an understaffed day (ERROR),
a rest-period violation (ERROR), and one person below their (overridden)
contract minimum (WARNING). See _seed_demo_schedule below.
"""

import asyncio
import calendar
import random
import uuid
from datetime import date, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.assignment import AssignmentSource
from app.models.availability import AvailabilityStatus
from app.models.rule import RulePhase, RuleScope, RuleSeverity, RuleType
from app.models.schedule_period import PeriodState
from app.models.shift_slot import ShiftSlot
from app.models.shift_type import ShiftType
from app.models.user import EmploymentType, Role, User
from app.repositories.assignment_repository import AssignmentRepository
from app.repositories.period_repository import PeriodRepository
from app.repositories.rule_repository import RuleRepository
from app.repositories.shift_type_repository import ShiftTypeRepository
from app.repositories.user_repository import UserRepository
from app.rules.weekdays import ALL_WEEKDAYS_MASK, WEEKEND_MASK, Weekday, weekday_of
from app.schemas.assignment import AssignmentCreate
from app.schemas.availability import AvailabilityEntryWrite
from app.schemas.period import PeriodCreate
from app.schemas.rule import RuleCreate
from app.schemas.shift_type import ShiftTypeCreate
from app.services.availability_service import AvailabilityService
from app.services.period_service import PeriodService
from app.services.rule_service import RuleService
from app.services.schedule_service import ScheduleService
from app.services.shift_type_service import ShiftTypeService

_SHIFT_TYPE_DEFS = [
    ShiftTypeCreate(
        code="MORNING",
        name_pl="Rano",
        name_en="Morning",
        start_time=time(7, 0),
        end_time=time(15, 0),
        color_hex="#fbbf24",
        active_weekdays=ALL_WEEKDAYS_MASK,
        default_required_staff=3,
        default_min_staff=2,
        default_max_staff=4,
        sort_order=0,
    ),
    ShiftTypeCreate(
        code="MIDDAY",
        name_pl="Poludnie",
        name_en="Midday",
        start_time=time(11, 0),
        end_time=time(19, 0),
        color_hex="#22c55e",
        active_weekdays=WEEKEND_MASK,
        default_required_staff=2,
        default_min_staff=1,
        default_max_staff=3,
        sort_order=1,
    ),
    ShiftTypeCreate(
        code="EVENING",
        name_pl="Wieczor",
        name_en="Evening",
        start_time=time(15, 0),
        end_time=time(23, 0),
        color_hex="#6366f1",
        active_weekdays=ALL_WEEKDAYS_MASK,
        default_required_staff=3,
        default_min_staff=2,
        default_max_staff=4,
        sort_order=2,
    ),
]

_RULE_DEFS = [
    RuleCreate(
        code="min_7_shifts",
        name_pl="Minimum 7 zadeklarowanych zmian",
        name_en="Minimum 7 declared shifts",
        type=RuleType.MIN_AVAILABILITY_COUNT,
        scope=RuleScope.GLOBAL,
        params={"n": 7},
        severity=RuleSeverity.HARD,
        phase=RulePhase.AVAILABILITY,
    ),
    RuleCreate(
        code="min_1_friday_evening",
        name_pl="Co najmniej 1 piatkowy wieczor",
        name_en="At least 1 Friday evening",
        type=RuleType.MIN_AVAILABILITY_IN_SET,
        scope=RuleScope.GLOBAL,
        params={"n": 1, "weekday": "FRI", "shift": "EVENING"},
        severity=RuleSeverity.HARD,
        phase=RulePhase.AVAILABILITY,
    ),
    # --- SCHEDULE-phase (ARCHITECTURE.md ss3.5 defaults) ---
    RuleCreate(
        code="one_shift_per_day",
        name_pl="Jedna zmiana dziennie",
        name_en="One shift per day",
        type=RuleType.ONE_SHIFT_PER_DAY,
        scope=RuleScope.GLOBAL,
        params={},
        severity=RuleSeverity.HARD,
        phase=RulePhase.SCHEDULE,
    ),
    RuleCreate(
        code="min_11h_rest",
        name_pl="Minimum 11 godzin odpoczynku",
        name_en="Minimum 11 hours rest",
        type=RuleType.MIN_REST_HOURS,
        scope=RuleScope.GLOBAL,
        params={"h": 11},
        severity=RuleSeverity.HARD,
        phase=RulePhase.SCHEDULE,
    ),
    RuleCreate(
        code="max_5_consecutive_days",
        name_pl="Maksymalnie 5 dni z rzedu",
        name_en="Maximum 5 consecutive days",
        type=RuleType.MAX_CONSECUTIVE_DAYS,
        scope=RuleScope.GLOBAL,
        params={"n": 5},
        severity=RuleSeverity.SOFT,
        phase=RulePhase.SCHEDULE,
    ),
    RuleCreate(
        code="min_5_shifts_per_month",
        name_pl="Minimum 5 zmian w miesiacu",
        name_en="Minimum 5 shifts per month",
        type=RuleType.MIN_SHIFTS_PER_MONTH,
        scope=RuleScope.GLOBAL,
        params={"n": 5},
        severity=RuleSeverity.SOFT,
        phase=RulePhase.SCHEDULE,
    ),
    RuleCreate(
        code="max_18_shifts_per_month",
        name_pl="Maksymalnie 18 zmian w miesiacu",
        name_en="Maximum 18 shifts per month",
        type=RuleType.MAX_SHIFTS_PER_MONTH,
        scope=RuleScope.GLOBAL,
        params={"n": 18},
        severity=RuleSeverity.SOFT,
        phase=RulePhase.SCHEDULE,
    ),
    RuleCreate(
        code="max_3_weekend_shifts",
        name_pl="Maksymalnie 3 zmiany weekendowe",
        name_en="Maximum 3 weekend shifts",
        type=RuleType.MAX_WEEKEND_SHIFTS,
        scope=RuleScope.GLOBAL,
        params={"n": 3},
        severity=RuleSeverity.SOFT,
        phase=RulePhase.SCHEDULE,
    ),
]

# One person deliberately kept below their own contract minimum (which
# overrides the min_5_shifts_per_month global default above) rather than the
# global one - proves the per-user override path, not just the rule itself.
_CONTRACT_MIN_OVERRIDE = 10
_CONTRACT_MIN_ACTUAL = 6

_EMPLOYEE_DEFS: list[tuple[str, str, EmploymentType]] = [
    ("employee01@example.com", "Anna Kowalska", EmploymentType.FULL_TIME),
    ("employee02@example.com", "Piotr Nowak", EmploymentType.PART_TIME),
    ("employee03@example.com", "Katarzyna Wisniewska", EmploymentType.STUDENT),
    ("employee04@example.com", "Tomasz Wojcik", EmploymentType.CASUAL),
    ("employee05@example.com", "Magdalena Kowalczyk", EmploymentType.FULL_TIME),
    ("employee06@example.com", "Michal Kaminski", EmploymentType.PART_TIME),
    ("employee07@example.com", "Agnieszka Lewandowska", EmploymentType.STUDENT),
    ("employee08@example.com", "Pawel Zielinski", EmploymentType.CASUAL),
    ("employee09@example.com", "Joanna Szymanska", EmploymentType.FULL_TIME),
    ("employee10@example.com", "Krzysztof Wozniak", EmploymentType.PART_TIME),
    ("employee11@example.com", "Ewa Dabrowska", EmploymentType.STUDENT),
    ("employee12@example.com", "Marcin Kozlowski", EmploymentType.CASUAL),
    ("employee13@example.com", "Natalia Jankowska", EmploymentType.FULL_TIME),
    ("employee14@example.com", "Lukasz Mazur", EmploymentType.PART_TIME),
    ("employee15@example.com", "Aleksandra Kwiatkowska", EmploymentType.STUDENT),
    ("employee16@example.com", "Grzegorz Wojciechowski", EmploymentType.CASUAL),
    ("employee17@example.com", "Monika Krawczyk", EmploymentType.FULL_TIME),
    ("employee18@example.com", "Adam Piotrowski", EmploymentType.PART_TIME),
]

_EMPLOYEE_PASSWORD = "password123"
# First N employees submit; the next few are left mid-edit (DRAFT); the rest
# are left untouched (NOT_STARTED) - so the manager's submission tracker has
# a realistic mix to look at instead of an all-green wall.
_SUBMITTED_COUNT = 12
_DRAFT_ONLY_COUNT = 16


async def _seed_admin(db: AsyncSession) -> User:
    assert settings.admin_bootstrap_password is not None  # guaranteed by get_settings()

    result = await db.execute(select(User).where(User.role == Role.ADMIN))
    existing_admin = result.scalars().first()
    if existing_admin is not None:
        # Don't print settings.admin_bootstrap_password here: if this admin's
        # password was ever changed via PATCH /users/me, that value is stale
        # and would mislead rather than help.
        print(f"Admin already exists ({existing_admin.email}); skipping creation.")
        print(f"Admin login -> email: {existing_admin.email}")
        print("Admin login -> password: unchanged from whenever it was last set")
        return existing_admin

    admin = User(
        email=settings.admin_bootstrap_email,
        password_hash=hash_password(settings.admin_bootstrap_password),
        full_name=settings.admin_bootstrap_full_name,
        role=Role.ADMIN,
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    print(f"Created bootstrap admin: {admin.email}")
    print(f"Admin login -> email: {admin.email}")
    print(f"Admin login -> password: {settings.admin_bootstrap_password}")
    return admin


async def _seed_shift_types(db: AsyncSession) -> list[ShiftType]:
    repo = ShiftTypeRepository(db)
    service = ShiftTypeService(db)
    shift_types = []
    for payload in _SHIFT_TYPE_DEFS:
        existing = await repo.get_by_code(payload.code)
        if existing is not None:
            shift_types.append(existing)
            continue
        shift_type = await service.create(payload)
        shift_types.append(shift_type)
        print(f"Created shift type: {shift_type.code}")
    return shift_types


async def _seed_rules(db: AsyncSession) -> None:
    repo = RuleRepository(db)
    service = RuleService(db)
    for payload in _RULE_DEFS:
        if await repo.get_by_code(payload.code) is not None:
            continue
        rule = await service.create(payload)
        print(f"Created rule: {rule.code}")


async def _seed_employees(db: AsyncSession) -> list[User]:
    repo = UserRepository(db)
    users = []
    created_count = 0
    for email, full_name, employment_type in _EMPLOYEE_DEFS:
        existing = await repo.get_by_email(email)
        if existing is not None:
            users.append(existing)
            continue
        user = User(
            email=email,
            password_hash=hash_password(_EMPLOYEE_PASSWORD),
            full_name=full_name,
            role=Role.EMPLOYEE,
            employment_type=employment_type,
            is_active=True,
        )
        await repo.create(user)
        users.append(user)
        created_count += 1
    await db.commit()
    for user in users:
        await db.refresh(user)
    if created_count:
        print(f"Created {created_count} demo employees (password: {_EMPLOYEE_PASSWORD}).")
    return users


def _next_month(today: date) -> tuple[int, int]:
    if today.month == 12:
        return today.year + 1, 1
    return today.year, today.month + 1


def _plausible_entries(
    rng: random.Random, slots: list[ShiftSlot], shift_types_by_id: dict[uuid.UUID, ShiftType]
) -> list[AvailabilityEntryWrite]:
    """A believable-looking month of availability: ~45% of open slots marked
    AVAILABLE/PREFERRED at random, then topped up (if needed) so it actually
    satisfies the demo rules - at least 8 declared shifts and at least one
    Friday evening - the same way a real, cooperative employee's would.
    """
    entries: dict[uuid.UUID, AvailabilityEntryWrite] = {}
    for slot in slots:
        if slot.is_closed:
            continue
        roll = rng.random()
        if roll < 0.40:
            continue  # UNAVAILABLE - simply no row
        status = AvailabilityStatus.PREFERRED if roll > 0.85 else AvailabilityStatus.AVAILABLE
        entries[slot.id] = AvailabilityEntryWrite(shift_slot_id=slot.id, status=status)

    if len(entries) < 8:
        candidates = [s for s in slots if not s.is_closed and s.id not in entries]
        rng.shuffle(candidates)
        for slot in candidates:
            if len(entries) >= 8:
                break
            entries[slot.id] = AvailabilityEntryWrite(
                shift_slot_id=slot.id, status=AvailabilityStatus.AVAILABLE
            )

    has_friday_evening = any(
        weekday_of(slot.date) == Weekday.FRI
        and shift_types_by_id[slot.shift_type_id].code == "EVENING"
        for slot in slots
        if slot.id in entries
    )
    if not has_friday_evening:
        friday_evenings = [
            s
            for s in slots
            if not s.is_closed
            and weekday_of(s.date) == Weekday.FRI
            and shift_types_by_id[s.shift_type_id].code == "EVENING"
        ]
        if friday_evenings:
            slot = rng.choice(friday_evenings)
            entries[slot.id] = AvailabilityEntryWrite(
                shift_slot_id=slot.id, status=AvailabilityStatus.AVAILABLE
            )

    return list(entries.values())


async def _seed_demo_period(db: AsyncSession, employees: list[User], *, actor: User) -> None:
    year, month = _next_month(date.today())
    period_service = PeriodService(db)

    period = await PeriodRepository(db).get_by_year_month(year, month)
    if period is None:
        period = await period_service.create(PeriodCreate(year=year, month=month))
        print(f"Created demo period {year}-{month:02d}")

    if period.state == PeriodState.DRAFT:
        period = await period_service.transition_state(period, PeriodState.COLLECTING, actor=actor)

    if period.state != PeriodState.COLLECTING:
        print(f"Demo period {year}-{month:02d} is past COLLECTING; skipping availability seed.")
        return

    slots = await period_service.list_slots(period.id)
    shift_types_by_id = {st.id: st for st in await ShiftTypeRepository(db).list_all()}
    availability_service = AvailabilityService(db)

    filled = 0
    for index, employee in enumerate(employees):
        if index >= _DRAFT_ONLY_COUNT:
            continue  # left NOT_STARTED, so the tracker has an empty state to show too
        entries = _plausible_entries(random.Random(1000 + index), slots, shift_types_by_id)
        await availability_service.write(user=employee, period=period, entries=entries)
        if index < _SUBMITTED_COUNT:
            await availability_service.submit(user=employee, period=period)
        filled += 1
    print(
        f"Seeded availability for {filled} employees on {year}-{month:02d}"
        f" ({_SUBMITTED_COUNT} submitted, {_DRAFT_ONLY_COUNT - _SUBMITTED_COUNT} left in draft,"
        f" {len(employees) - _DRAFT_ONLY_COUNT} left not started)."
    )


def _all_dates(year: int, month: int) -> list[date]:
    days_in_month = calendar.monthrange(year, month)[1]
    return [date(year, month, day) for day in range(1, days_in_month + 1)]


async def _seed_demo_schedule(db: AsyncSession, employees: list[User], *, actor: User) -> None:
    """A second demo period - the CURRENT month, distinct from next month's
    COLLECTING one above - already advanced to GENERATED with a handful of
    manual assignments. Deliberately left mostly unassigned (a manager
    mid-way through manual scheduling, not a finished month) except for
    three targeted scenarios: see module docstring.
    """
    year, month = date.today().year, date.today().month
    period_service = PeriodService(db)

    period = await PeriodRepository(db).get_by_year_month(year, month)
    if period is None:
        period = await period_service.create(PeriodCreate(year=year, month=month))
        print(f"Created demo schedule period {year}-{month:02d}")

    order = [
        PeriodState.DRAFT,
        PeriodState.COLLECTING,
        PeriodState.LOCKED,
        PeriodState.GENERATED,
        PeriodState.PUBLISHED,
    ]
    if order.index(period.state) > order.index(PeriodState.GENERATED):
        print(f"Demo schedule period {year}-{month:02d} is past GENERATED; skipping.")
        return
    while period.state != PeriodState.GENERATED:
        period = await period_service.transition_state(
            period, order[order.index(period.state) + 1], actor=actor
        )

    if await AssignmentRepository(db).list_by_period(period.id):
        print(f"Demo schedule period {year}-{month:02d} already has assignments; skipping.")
        return

    slots = await period_service.list_slots(period.id)
    shift_types_by_id = {st.id: st for st in await ShiftTypeRepository(db).list_all()}
    slot_by_date_and_code = {
        (slot.date, shift_types_by_id[slot.shift_type_id].code): slot for slot in slots
    }
    schedule_service = ScheduleService(db)

    async def _assign(employee: User, slot: ShiftSlot) -> None:
        await schedule_service.create_assignment(
            period,
            AssignmentCreate(
                shift_slot_id=slot.id, user_id=employee.id, source=AssignmentSource.MANUAL
            ),
            actor=actor,
        )

    # Scenario 1: below (overridden) contract minimum. Anna's personal
    # contract_min_shifts (10) is stricter than the global min_5_shifts rule,
    # and her 6 assigned shifts clear that global default but not her own -
    # proving the per-user override actually takes effect.
    contract_employee = employees[0]
    contract_employee.contract_min_shifts = _CONTRACT_MIN_OVERRIDE
    await UserRepository(db).save(contract_employee)
    await db.commit()

    weekdays = [
        d for d in _all_dates(year, month) if weekday_of(d) not in (Weekday.SAT, Weekday.SUN)
    ]
    for d in weekdays[::3][:_CONTRACT_MIN_ACTUAL]:
        slot = slot_by_date_and_code.get((d, "MORNING"))
        if slot is not None:
            await _assign(contract_employee, slot)

    # Scenario 2: rest-period violation. Piotr works the first EVENING shift
    # of the month then the very next MORNING shift - 8 hours of rest,
    # short of the 11-hour min_11h_rest rule.
    rest_employee = employees[1]
    rest_day = next(
        d
        for d in _all_dates(year, month)
        if (d, "EVENING") in slot_by_date_and_code
        and (d + timedelta(days=1), "MORNING") in slot_by_date_and_code
    )
    await _assign(rest_employee, slot_by_date_and_code[(rest_day, "EVENING")])
    await _assign(rest_employee, slot_by_date_and_code[(rest_day + timedelta(days=1), "MORNING")])

    # Scenario 3: understaffed day. EVENING's default min_staff is 2 - one
    # person here is deliberately below that minimum (an ERROR, not just a
    # WARNING, since it's below min_staff rather than merely below
    # required_staff).
    understaffed_employee = employees[2]
    rest_dates = (rest_day, rest_day + timedelta(days=1))
    understaffed_day = next(
        d
        for d in _all_dates(year, month)
        if (d, "EVENING") in slot_by_date_and_code and d not in rest_dates
    )
    await _assign(understaffed_employee, slot_by_date_and_code[(understaffed_day, "EVENING")])

    print(
        f"Seeded demo schedule for {year}-{month:02d}: "
        f"{contract_employee.full_name} has {_CONTRACT_MIN_ACTUAL}/{_CONTRACT_MIN_OVERRIDE} "
        "contract shifts, "
        f"{rest_employee.full_name} has a rest violation on "
        f"{rest_day.isoformat()} -> {(rest_day + timedelta(days=1)).isoformat()}, "
        f"{understaffed_employee.full_name}'s {understaffed_day.isoformat()} EVENING shift "
        "is understaffed below minimum."
    )


async def run() -> None:
    async with SessionLocal() as db:
        admin = await _seed_admin(db)
        await _seed_shift_types(db)
        await _seed_rules(db)
        employees = await _seed_employees(db)
        await _seed_demo_period(db, employees, actor=admin)
        await _seed_demo_schedule(db, employees, actor=admin)


if __name__ == "__main__":
    asyncio.run(run())
