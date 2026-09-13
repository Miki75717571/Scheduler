"""Real configuration + (optional) demo data bootstrap.

Two tiers, run every time `uv run python -m app.seed` is invoked:

1. **Real config - always seeded, never gated.** The bootstrap ADMIN user,
   the three real ShiftTypes (MORNING/MIDDAY/EVENING) with their per-weekday
   overrides, the real availability/schedule Rule values, and the four
   ScoreCriterion rows. This is the owner's actual cafeteria configuration,
   not a demo - see the values' rationale inline below.
2. **Demo data - only when `settings.seed_demo_data` is true.** ~18 fake
   employees, a demo SchedulePeriod with plausible availability, a second
   demo period advanced to GENERATED with deliberate violations, and demo
   scores. `start.ps1` never sets this flag, so a fresh clone/real deploy
   never gets fake employees; run `SEED_DEMO_DATA=1 uv run python -m
   app.seed` explicitly to get a demo month to click through.

Idempotent throughout: re-running skips/updates rather than duplicating or
crashing (matched by code/email/year+month, or upserted for overrides).
"""

import asyncio
import calendar
import random
import uuid
from datetime import date, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.assignment import AssignmentSource
from app.models.availability import AvailabilityStatus
from app.models.rule import RulePhase, RuleScope, RuleSeverity, RuleType
from app.models.schedule_period import PeriodState
from app.models.score_criterion import ScoreCriterion
from app.models.shift_slot import ShiftSlot
from app.models.shift_type import ShiftType
from app.models.user import EmploymentType, Role, User
from app.repositories.assignment_repository import AssignmentRepository
from app.repositories.employee_score_repository import EmployeeScoreRepository
from app.repositories.period_repository import PeriodRepository
from app.repositories.rule_repository import RuleRepository
from app.repositories.score_criterion_repository import ScoreCriterionRepository
from app.repositories.shift_type_repository import ShiftTypeRepository
from app.repositories.user_repository import UserRepository
from app.rules.weekdays import ALL_WEEKDAYS_MASK, WEEKEND_MASK, Weekday, weekday_of
from app.schemas.assignment import AssignmentCreate
from app.schemas.availability import AvailabilityEntryWrite
from app.schemas.employee_score import EmployeeScoreCreate
from app.schemas.period import PeriodCreate
from app.schemas.rule import RuleCreate, RuleUpdate
from app.schemas.score_criterion import (
    ScoreCriterionCreate,
    ScoreWeightsUpdate,
    ScoreWeightsUpdateItem,
)
from app.schemas.shift_type import ShiftTypeCreate, ShiftTypeUpdate, ShiftTypeWeekdayOverrideWrite
from app.services.availability_service import AvailabilityService
from app.services.period_service import PeriodService
from app.services.rule_service import RuleService
from app.services.schedule_service import ScheduleService
from app.services.score_service import ScoreService
from app.services.shift_type_service import ShiftTypeService

# The owner's real cafeteria: open 7 days/week, exactly one person per shift
# (min=required=max=1 everywhere - see CLAUDE.md JOB 2/6). Each ShiftType's
# own start_time/end_time/staff triple below is also its Mon-Thu (and, for
# MORNING/EVENING, Sat-Sun) value; only Friday runs later, so that's the only
# day that needs an explicit override row (see _SHIFT_TYPE_OVERRIDE_DEFS) -
# every other active weekday falls back to these defaults untouched
# (app/services/shift_effective.py's `resolve_effective_config`).
_SHIFT_TYPE_DEFS = [
    ShiftTypeCreate(
        code="MORNING",
        name_pl="Rano",
        name_en="Morning",
        start_time=time(8, 30),
        end_time=time(14, 0),
        color_hex="#fbbf24",
        active_weekdays=ALL_WEEKDAYS_MASK,
        default_required_staff=1,
        default_min_staff=1,
        default_max_staff=1,
        sort_order=0,
    ),
    ShiftTypeCreate(
        code="MIDDAY",
        name_pl="Poludnie",
        name_en="Midday",
        # Weekend-only and deliberately overlapping MORNING/EVENING - two
        # people on at once during the busiest part of a weekend day. Not a
        # mistake; see CLAUDE.md JOB 2.
        start_time=time(10, 0),
        end_time=time(17, 0),
        color_hex="#22c55e",
        active_weekdays=WEEKEND_MASK,
        default_required_staff=1,
        default_min_staff=1,
        default_max_staff=1,
        sort_order=1,
    ),
    ShiftTypeCreate(
        code="EVENING",
        name_pl="Wieczor",
        name_en="Evening",
        start_time=time(14, 0),
        end_time=time(20, 0),
        color_hex="#6366f1",
        active_weekdays=ALL_WEEKDAYS_MASK,
        default_required_staff=1,
        default_min_staff=1,
        default_max_staff=1,
        sort_order=2,
    ),
]

# Only Friday differs from the ShiftType defaults above - MORNING/EVENING
# both run later, closing at 22:00 instead of 20:00. This is also exactly the
# pair that creates the MIN_REST_HOURS conflict called out in CLAUDE.md JOB 4
# (Friday EVENING 22:00 -> Saturday MORNING 08:30 is a 10.5h gap, under the
# 11h min_11h_rest rule below) - see app/rules/rest_conflicts.py.
_SHIFT_TYPE_OVERRIDE_DEFS: list[tuple[str, Weekday, ShiftTypeWeekdayOverrideWrite]] = [
    (
        "MORNING",
        Weekday.FRI,
        ShiftTypeWeekdayOverrideWrite(
            start_time=time(8, 30), end_time=time(15, 0), min_staff=1, required_staff=1, max_staff=1
        ),
    ),
    (
        "EVENING",
        Weekday.FRI,
        ShiftTypeWeekdayOverrideWrite(
            start_time=time(15, 0), end_time=time(22, 0), min_staff=1, required_staff=1, max_staff=1
        ),
    ),
]

# 7 employees, ~70 slots/month => ~10 shifts/employee on average. Every
# threshold below is sized for that, not for a larger crew - see the
# min_15_availability comment for the one that's easy to get wrong.
_RULE_DEFS = [
    # 70 slots / 7 people = 10 shifts each needed. If MIN_AVAILABILITY_COUNT
    # were left at the old default of 7 (one per person), the whole month
    # would be mathematically unfillable: 7 employees x 7 declarations = 49
    # declarations for 70 slots. 15 each gives 105 declarations for 70 slots,
    # leaving the solver enough real choice to balance fairness/preferences
    # instead of being forced into the one and only feasible assignment (or
    # no feasible assignment at all). Do not lower this without re-deriving
    # the math for the current employee count and slot count.
    RuleCreate(
        code="min_15_availability",
        name_pl="Minimum 15 zadeklarowanych zmian",
        name_en="Minimum 15 declared shifts",
        type=RuleType.MIN_AVAILABILITY_COUNT,
        scope=RuleScope.GLOBAL,
        params={"n": 15},
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
    # --- SCHEDULE-phase ---
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
    # Kept at 11h (Polish labour law's daily rest minimum) even though it
    # makes Friday EVENING -> Saturday MORNING impossible for the same
    # person (10.5h gap) - a deliberate trade-off, surfaced rather than
    # silently resolved. See CLAUDE.md JOB 4: editable in the admin rules
    # screen, and the conflict is flagged both there and in solver
    # diagnostics (app/rules/rest_conflicts.py) rather than being papered
    # over by quietly loosening this number.
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
        code="min_8_shifts_per_month",
        name_pl="Minimum 8 zmian w miesiacu",
        name_en="Minimum 8 shifts per month",
        type=RuleType.MIN_SHIFTS_PER_MONTH,
        scope=RuleScope.GLOBAL,
        params={"n": 8},
        severity=RuleSeverity.SOFT,
        phase=RulePhase.SCHEDULE,
    ),
    RuleCreate(
        code="max_13_shifts_per_month",
        name_pl="Maksymalnie 13 zmian w miesiacu",
        name_en="Maximum 13 shifts per month",
        type=RuleType.MAX_SHIFTS_PER_MONTH,
        scope=RuleScope.GLOBAL,
        params={"n": 13},
        severity=RuleSeverity.SOFT,
        phase=RulePhase.SCHEDULE,
    ),
    # ~26 weekend slots / 7 people = ~3.7 each; anything below 4 makes the
    # month impossible, so this is set to 5 for real slack (CLAUDE.md JOB 3).
    RuleCreate(
        code="max_5_weekend_shifts",
        name_pl="Maksymalnie 5 zmian weekendowych",
        name_en="Maximum 5 weekend shifts",
        type=RuleType.MAX_WEEKEND_SHIFTS,
        scope=RuleScope.GLOBAL,
        params={"n": 5},
        severity=RuleSeverity.SOFT,
        phase=RulePhase.SCHEDULE,
    ),
]

# Phase 4 (ARCHITECTURE.md ss3.4) defaults - a starting point the owner said
# they will change, so nothing downstream (app/services/score_service.py,
# the manager scoring grid) may special-case these codes. Weights sum to
# exactly 1.0, as required for a composite to be computable at all.
_SCORE_CRITERION_DEFS = [
    ScoreCriterionCreate(
        code="CUSTOMER_SERVICE",
        name_pl="Obsluga klienta",
        name_en="Customer service",
        description="Warmth and helpfulness with customers.",
        weight=Decimal("0.35"),
        is_active=True,
    ),
    ScoreCriterionCreate(
        code="RELIABILITY",
        name_pl="Niezawodnosc",
        name_en="Reliability",
        description="Shows up on time, rarely calls in sick or swaps last-minute.",
        weight=Decimal("0.35"),
        is_active=True,
    ),
    ScoreCriterionCreate(
        code="SPEED",
        name_pl="Szybkosc",
        name_en="Speed",
        description="Keeps up during rushes without cutting corners.",
        weight=Decimal("0.15"),
        is_active=True,
    ),
    ScoreCriterionCreate(
        code="SENIORITY",
        name_pl="Staz pracy",
        name_en="Seniority",
        description="Experience and tenure at the cafeteria.",
        weight=Decimal("0.15"),
        is_active=True,
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


def _shift_type_differs(existing: ShiftType, payload: ShiftTypeCreate) -> bool:
    return (
        existing.start_time != payload.start_time
        or existing.end_time != payload.end_time
        or existing.active_weekdays != payload.active_weekdays
        or existing.default_required_staff != payload.default_required_staff
        or existing.default_min_staff != payload.default_min_staff
        or existing.default_max_staff != payload.default_max_staff
    )


async def _seed_shift_types(db: AsyncSession) -> list[ShiftType]:
    """Unlike most of this module's seeders, an existing row is UPDATED to
    match `_SHIFT_TYPE_DEFS`, not left alone - CLAUDE.md JOB 2 is explicitly
    about replacing whatever demo times/staffing an already-seeded database
    has with the owner's real ones, not just filling in what's missing.
    """
    repo = ShiftTypeRepository(db)
    service = ShiftTypeService(db)
    shift_types = []
    for payload in _SHIFT_TYPE_DEFS:
        existing = await repo.get_by_code(payload.code)
        if existing is None:
            shift_type = await service.create(payload)
            shift_types.append(shift_type)
            print(f"Created shift type: {shift_type.code}")
            continue
        if _shift_type_differs(existing, payload):
            shift_type = await service.update(
                existing.id,
                ShiftTypeUpdate(
                    start_time=payload.start_time,
                    end_time=payload.end_time,
                    active_weekdays=payload.active_weekdays,
                    default_required_staff=payload.default_required_staff,
                    default_min_staff=payload.default_min_staff,
                    default_max_staff=payload.default_max_staff,
                ),
            )
            print(f"Updated shift type to real config: {shift_type.code}")
        else:
            shift_type = existing
        shift_types.append(shift_type)
    return shift_types


async def _seed_shift_type_overrides(db: AsyncSession, shift_types: list[ShiftType]) -> None:
    service = ShiftTypeService(db)
    shift_types_by_code = {st.code: st for st in shift_types}
    for code, weekday, payload in _SHIFT_TYPE_OVERRIDE_DEFS:
        shift_type = shift_types_by_code[code]
        await service.upsert_override(shift_type.id, weekday, payload)
    print(f"Set {len(_SHIFT_TYPE_OVERRIDE_DEFS)} shift type weekday override(s).")


async def _seed_rules(db: AsyncSession) -> None:
    repo = RuleRepository(db)
    service = RuleService(db)
    for payload in _RULE_DEFS:
        if await repo.get_by_code(payload.code) is not None:
            continue
        rule = await service.create(payload)
        print(f"Created rule: {rule.code}")
    await _deactivate_legacy_rules(db)


# Rule codes replaced by CLAUDE.md JOB 3's real values (`_RULE_DEFS` above) -
# an already-seeded database (this project's own dev DB before this change)
# would otherwise end up with BOTH the old and new rows active at once for
# the same rule type, silently applying two conflicting thresholds. Never
# deleted (CLAUDE.md: audit history survives), just deactivated like any
# other superseded row in this codebase.
_LEGACY_RULE_CODES = [
    "min_7_shifts",
    "min_5_shifts_per_month",
    "max_18_shifts_per_month",
    "max_3_weekend_shifts",
]


async def _deactivate_legacy_rules(db: AsyncSession) -> None:
    repo = RuleRepository(db)
    service = RuleService(db)
    for code in _LEGACY_RULE_CODES:
        rule = await repo.get_by_code(code)
        if rule is None or not rule.is_active:
            continue
        await service.update(rule.id, RuleUpdate(is_active=False))
        print(f"Deactivated superseded rule: {code}")


async def _seed_score_criteria(db: AsyncSession) -> None:
    """Creates each default criterion inactive at weight 0 first, then
    activates all four together at their real weights in one bulk call -
    creating them active one at a time would violate the "active weights sum
    to 1.0" invariant at every step but the last (see
    app/schemas/score_criterion.py's ScoreWeightsUpdate docstring).
    """
    repo = ScoreCriterionRepository(db)
    service = ScoreService(db)

    pending: list[tuple[ScoreCriterion, Decimal]] = []
    any_created = False
    for payload in _SCORE_CRITERION_DEFS:
        existing = await repo.get_by_code(payload.code)
        if existing is not None:
            pending.append((existing, payload.weight))
            continue
        draft = payload.model_copy(update={"weight": Decimal("0"), "is_active": False})
        criterion = await service.create_criterion(draft)
        pending.append((criterion, payload.weight))
        any_created = True
        print(f"Created score criterion: {criterion.code}")

    if any_created:
        await service.update_weights(
            ScoreWeightsUpdate(
                items=[
                    ScoreWeightsUpdateItem(id=criterion.id, weight=weight, is_active=True)
                    for criterion, weight in pending
                ]
            )
        )


# Every third employee is left unscored on SPEED, so the grid's "not yet
# rated" cell and the None composite have something to show.
_SCORE_VALUE_BY_INDEX_MOD = {0: 5, 1: 4, 2: 3, 3: 2}


async def _seed_demo_scores(db: AsyncSession, employees: list[User], *, actor: User) -> None:
    criteria = await ScoreCriterionRepository(db).list_all(active_only=True)
    if not criteria:
        return
    score_service = ScoreService(db)

    existing = await EmployeeScoreRepository(db).list_effective_rows(
        {e.id for e in employees}, as_of=date.today()
    )
    if existing:
        print("Demo scores already seeded; skipping.")
        return

    scored_count = 0
    for index, employee in enumerate(employees):
        for criterion_index, criterion in enumerate(criteria):
            if criterion.code == "SPEED" and index % 3 == 0:
                continue  # deliberately left unrated
            value = _SCORE_VALUE_BY_INDEX_MOD[(index + criterion_index) % 4]
            await score_service.set_score(
                user_id=employee.id,
                payload=EmployeeScoreCreate(criterion_id=criterion.id, value=value),
                actor=actor,
            )
        scored_count += 1
    print(f"Seeded demo scores for {scored_count} employees across {len(criteria)} criteria.")


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
    mid-way through manual scheduling, not a finished month), which itself
    already demonstrates understaffing (ERROR) everywhere it's untouched -
    see the two additional targeted scenarios below.
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
    # contract_min_shifts (10) is stricter than the global min_8_shifts rule,
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

    # Scenario 2: rest-period violation. Piotr works a Friday EVENING shift
    # (ends 22:00, see the Friday override in _SHIFT_TYPE_OVERRIDE_DEFS) then
    # the very next (Saturday) MORNING shift (starts 08:30) - 10.5 hours of
    # rest, short of the 11-hour min_11h_rest rule. This is the same
    # structural conflict CLAUDE.md JOB 4 asks to surface, not hide - picking
    # Friday->Saturday specifically (rather than "the first EVENING shift of
    # the month") is what makes this scenario deterministic: every other
    # weekday's EVENING->next-MORNING gap is a legal 12.5 hours.
    rest_employee = employees[1]
    rest_day = next(
        d
        for d in _all_dates(year, month)
        if weekday_of(d) == Weekday.FRI
        and (d, "EVENING") in slot_by_date_and_code
        and (d + timedelta(days=1), "MORNING") in slot_by_date_and_code
    )
    await _assign(rest_employee, slot_by_date_and_code[(rest_day, "EVENING")])
    await _assign(rest_employee, slot_by_date_and_code[(rest_day + timedelta(days=1), "MORNING")])

    # No separate "understaffed" scenario: with one-person shifts
    # (min_staff = required_staff = 1, CLAUDE.md JOB 6b), staffing is binary
    # - every one of the many slots this demo period leaves untouched is
    # already 0/1 assigned, i.e. already understaffed below minimum. The
    # partial-fill "assigned but still below minimum" case this scenario
    # used to demonstrate no longer exists at this staffing level.
    print(
        f"Seeded demo schedule for {year}-{month:02d}: "
        f"{contract_employee.full_name} has {_CONTRACT_MIN_ACTUAL}/{_CONTRACT_MIN_OVERRIDE} "
        "contract shifts, "
        f"{rest_employee.full_name} has a rest violation on "
        f"{rest_day.isoformat()} (Friday EVENING) -> "
        f"{(rest_day + timedelta(days=1)).isoformat()} (Saturday MORNING), "
        "and every other open shift this month is left unassigned (already "
        "understaffed below minimum, since min_staff = 1)."
    )


async def run() -> None:
    async with SessionLocal() as db:
        # Real config - always seeded, every run, regardless of
        # SEED_DEMO_DATA (CLAUDE.md JOB 7).
        admin = await _seed_admin(db)
        shift_types = await _seed_shift_types(db)
        await _seed_shift_type_overrides(db, shift_types)
        await _seed_rules(db)
        await _seed_score_criteria(db)

        if not settings.seed_demo_data:
            print("SEED_DEMO_DATA is off; skipping fake employees/period/schedule/scores.")
            return

        # Demo data - explicit opt-in only, never on a fresh clone or a real
        # deploy (see app/core/config.py's `seed_demo_data`).
        employees = await _seed_employees(db)
        await _seed_demo_period(db, employees, actor=admin)
        await _seed_demo_schedule(db, employees, actor=admin)
        await _seed_demo_scores(db, employees, actor=admin)


if __name__ == "__main__":
    asyncio.run(run())
