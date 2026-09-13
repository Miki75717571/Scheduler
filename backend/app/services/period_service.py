import calendar
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.availability import AvailabilityStatus, AvailabilitySubmission, SubmissionStatus
from app.models.rule import RulePhase, RuleScope, RuleType
from app.models.schedule_period import PeriodState, SchedulePeriod
from app.models.shift_slot import ShiftSlot
from app.models.shift_type import ShiftType
from app.models.shift_type_weekday_override import ShiftTypeWeekdayOverride
from app.models.user import Role, User
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.availability_repository import AvailabilityRepository
from app.repositories.period_repository import PeriodRepository
from app.repositories.rule_repository import RuleRepository
from app.repositories.shift_slot_repository import ShiftSlotRepository
from app.repositories.shift_type_repository import ShiftTypeRepository
from app.repositories.user_repository import UserRepository
from app.rules.weekdays import Weekday, active_on, is_weekend
from app.schemas.period import PeriodCreate
from app.schemas.shift_slot import ShiftSlotRead, ShiftSlotUpdate
from app.services.shift_effective import overrides_by_weekday_for, resolve_effective_config


@dataclass(frozen=True)
class NotSubmittedEmployee:
    user_id: uuid.UUID
    full_name: str
    estimated_slots_uncovered: int


@dataclass(frozen=True)
class FeasibilitySummary:
    total_slots: int
    active_employee_count: int
    avg_shifts_per_employee: float
    min_shifts_per_month: int | None
    max_weekend_shifts: int | None
    weekend_slot_count: int
    total_declared: int
    min_shifts_feasible: bool
    availability_feasible: bool | None  # None until any submission exists
    weekend_feasible: bool
    not_submitted: list[NotSubmittedEmployee] = field(default_factory=list)


class PeriodError(Exception):
    def __init__(self, message_key: str, params: dict[str, Any] | None = None) -> None:
        self.message_key = message_key
        self.params = params or {}
        super().__init__(message_key)


# Strictly forward, one step at a time - see CLAUDE.md/ARCHITECTURE.md's state
# machine. Backward moves are never a full-period transition; the one
# supported "undo" is the per-employee reopen action in AvailabilityService.
_LEGAL_TRANSITIONS: dict[PeriodState, PeriodState] = {
    PeriodState.DRAFT: PeriodState.COLLECTING,
    PeriodState.COLLECTING: PeriodState.LOCKED,
    PeriodState.LOCKED: PeriodState.GENERATED,
    PeriodState.GENERATED: PeriodState.PUBLISHED,
}


def _generate_slots(
    period: SchedulePeriod,
    shift_types: list[ShiftType],
    overrides_by_type: dict[uuid.UUID, dict[Weekday, ShiftTypeWeekdayOverride]],
) -> list[ShiftSlot]:
    days_in_month = calendar.monthrange(period.year, period.month)[1]
    slots: list[ShiftSlot] = []
    for day in range(1, days_in_month + 1):
        current = date(period.year, period.month, day)
        for shift_type in shift_types:
            if not active_on(shift_type.active_weekdays, current):
                continue
            # Staffing levels are resolved per-weekday at generation time and
            # then live on the slot itself (editable per day afterward) - see
            # app/services/shift_effective.py. Clock times are NOT copied
            # here: ShiftSlot never stores its own time, so a later edit to a
            # ShiftTypeWeekdayOverride still applies retroactively to every
            # slot on that weekday (resolved fresh at read time instead).
            effective = resolve_effective_config(
                shift_type, overrides_by_type.get(shift_type.id, {}), current
            )
            slots.append(
                ShiftSlot(
                    period_id=period.id,
                    date=current,
                    shift_type_id=shift_type.id,
                    required_staff=effective.required_staff,
                    min_staff=effective.min_staff,
                    max_staff=effective.max_staff,
                )
            )
    return slots


class PeriodService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._periods = PeriodRepository(db)
        self._slots = ShiftSlotRepository(db)
        self._shift_types = ShiftTypeRepository(db)
        self._users = UserRepository(db)
        self._availability = AvailabilityRepository(db)
        self._audit_log = AuditLogRepository(db)
        self._rules = RuleRepository(db)

    async def create(self, payload: PeriodCreate) -> SchedulePeriod:
        if await self._periods.get_by_year_month(payload.year, payload.month) is not None:
            raise PeriodError("period.already_exists")

        period = SchedulePeriod(
            year=payload.year,
            month=payload.month,
            availability_opens_at=payload.availability_opens_at,
            availability_deadline=payload.availability_deadline,
        )
        await self._periods.create(period)

        shift_types = await self._shift_types.list_all(active_only=True)
        overrides_by_type = await self._overrides_by_type({st.id for st in shift_types})
        slots = _generate_slots(period, shift_types, overrides_by_type)
        await self._slots.create_many(slots)

        await self._db.commit()
        await self._db.refresh(period)
        return period

    async def get(self, period_id: uuid.UUID) -> SchedulePeriod:
        period = await self._periods.get_by_id(period_id)
        if period is None:
            raise PeriodError("period.not_found")
        return period

    async def list_all(self) -> list[SchedulePeriod]:
        return await self._periods.list_all()

    async def transition_state(
        self,
        period: SchedulePeriod,
        target: PeriodState,
        *,
        actor: User,
        override_used: bool = False,
    ) -> SchedulePeriod:
        expected_next = _LEGAL_TRANSITIONS.get(period.state)
        if expected_next != target:
            raise PeriodError(
                "period.illegal_transition", {"from": period.state.value, "to": target.value}
            )

        previous_state = period.state
        period.state = target
        if target == PeriodState.COLLECTING:
            await self._ensure_submissions_for_active_users(period)
        elif target == PeriodState.PUBLISHED:
            period.published_at = datetime.now(UTC)
            period.published_by_user_id = actor.id
            await self._audit_log.create(
                AuditLog(
                    actor_user_id=actor.id,
                    period_id=period.id,
                    action="period.publish_override" if override_used else "period.publish",
                    entity_type="SchedulePeriod",
                    entity_id=period.id,
                    before={"state": previous_state.value},
                    after={"state": target.value, "override_used": override_used},
                )
            )

        await self._periods.save(period)
        await self._db.commit()
        await self._db.refresh(period)
        return period

    async def _ensure_submissions_for_active_users(self, period: SchedulePeriod) -> None:
        active_users = [u for u in await self._users.list_all() if u.is_active]
        existing = await self._availability.list_submissions_for_period(period.id)
        existing_user_ids = {s.user_id for s in existing}
        for user in active_users:
            if user.id not in existing_user_ids:
                await self._availability.create_submission(
                    AvailabilitySubmission(
                        user_id=user.id, period_id=period.id, status=SubmissionStatus.NOT_STARTED
                    )
                )

    async def list_slots(self, period_id: uuid.UUID) -> list[ShiftSlot]:
        return await self._slots.list_by_period(period_id)

    async def _overrides_by_type(
        self, shift_type_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, dict[Weekday, ShiftTypeWeekdayOverride]]:
        overrides = await self._shift_types.list_overrides_for_types(shift_type_ids)
        by_type: dict[uuid.UUID, list[ShiftTypeWeekdayOverride]] = defaultdict(list)
        for override in overrides:
            by_type[override.shift_type_id].append(override)
        return {type_id: overrides_by_weekday_for(rows) for type_id, rows in by_type.items()}

    def _to_slot_read(
        self,
        slot: ShiftSlot,
        shift_types_by_id: dict[uuid.UUID, ShiftType],
        overrides_by_type: dict[uuid.UUID, dict[Weekday, ShiftTypeWeekdayOverride]],
    ) -> ShiftSlotRead:
        shift_type = shift_types_by_id[slot.shift_type_id]
        effective = resolve_effective_config(
            shift_type, overrides_by_type.get(shift_type.id, {}), slot.date
        )
        return ShiftSlotRead(
            id=slot.id,
            period_id=slot.period_id,
            date=slot.date,
            shift_type_id=slot.shift_type_id,
            required_staff=slot.required_staff,
            min_staff=slot.min_staff,
            max_staff=slot.max_staff,
            is_closed=slot.is_closed,
            note=slot.note,
            start_time=effective.start_time,
            end_time=effective.end_time,
        )

    async def to_slot_read(self, slot: ShiftSlot) -> ShiftSlotRead:
        shift_types_by_id = {st.id: st for st in await self._shift_types.list_all()}
        overrides_by_type = await self._overrides_by_type({slot.shift_type_id})
        return self._to_slot_read(slot, shift_types_by_id, overrides_by_type)

    async def list_slots_read(self, period_id: uuid.UUID) -> list[ShiftSlotRead]:
        slots = await self.list_slots(period_id)
        shift_types_by_id = {st.id: st for st in await self._shift_types.list_all()}
        overrides_by_type = await self._overrides_by_type({s.shift_type_id for s in slots})
        return [self._to_slot_read(s, shift_types_by_id, overrides_by_type) for s in slots]

    async def update_slot(
        self, period: SchedulePeriod, slot_id: uuid.UUID, payload: ShiftSlotUpdate
    ) -> ShiftSlot:
        slot = await self._slots.get_by_id(slot_id)
        if slot is None or slot.period_id != period.id:
            raise PeriodError("shift_slot.not_found")

        for slot_field, value in payload.model_dump(exclude_unset=True).items():
            setattr(slot, slot_field, value)
        if not (slot.min_staff <= slot.required_staff <= slot.max_staff):
            raise PeriodError("shift_slot.invalid_staff_levels")

        await self._slots.save(slot)
        await self._db.commit()
        await self._db.refresh(slot)
        return slot

    # --- feasibility pre-check (CLAUDE.md JOB 5) ----------------------------

    async def feasibility_summary(self, period: SchedulePeriod) -> FeasibilitySummary:
        """Plain-language answers to "can this month even be filled" - meant
        to be read by the manager BEFORE hitting generate, not after. With a
        small team (CLAUDE.md's "7 people, this system is fragile") one
        person on holiday removes a meaningful fraction of total capacity;
        this makes that visible up front instead of as a mysterious solver
        failure later.
        """
        slots = [s for s in await self._slots.list_by_period(period.id) if not s.is_closed]
        total_slots = len(slots)
        weekend_slot_count = sum(1 for s in slots if is_weekend(s.date))

        active_employees = [
            u for u in await self._users.list_all() if u.is_active and u.role == Role.EMPLOYEE
        ]
        active_employee_count = len(active_employees)
        avg_shifts_per_employee = (
            total_slots / active_employee_count if active_employee_count else 0.0
        )

        schedule_rules = await self._rules.list_active_by_phase(RulePhase.SCHEDULE)
        min_shifts_rules = [
            r
            for r in schedule_rules
            if r.type == RuleType.MIN_SHIFTS_PER_MONTH and r.scope == RuleScope.GLOBAL
        ]
        max_weekend_rules = [
            r
            for r in schedule_rules
            if r.type == RuleType.MAX_WEEKEND_SHIFTS and r.scope == RuleScope.GLOBAL
        ]
        min_shifts_per_month = int(min_shifts_rules[0].params["n"]) if min_shifts_rules else None
        max_weekend_shifts = int(max_weekend_rules[0].params["n"]) if max_weekend_rules else None

        min_shifts_feasible = (
            min_shifts_per_month is None
            or active_employee_count * min_shifts_per_month <= total_slots
        )
        weekend_feasible = (
            max_weekend_shifts is None
            or weekend_slot_count <= active_employee_count * max_weekend_shifts
        )

        availability_rows = await self._availability.list_entries_for_slots([s.id for s in slots])
        total_declared = sum(
            1
            for _, _, status in availability_rows
            if status in (AvailabilityStatus.AVAILABLE, AvailabilityStatus.PREFERRED)
        )
        submissions = await self._availability.list_submissions_for_period(period.id)
        any_submission_started = any(s.status != SubmissionStatus.NOT_STARTED for s in submissions)
        availability_feasible = (total_declared >= total_slots) if any_submission_started else None

        submitted_user_ids = {
            s.user_id for s in submissions if s.status == SubmissionStatus.SUBMITTED
        }
        per_employee_share = (
            round(total_slots / active_employee_count) if active_employee_count else 0
        )
        not_submitted = [
            NotSubmittedEmployee(
                user_id=employee.id,
                full_name=employee.full_name,
                estimated_slots_uncovered=per_employee_share,
            )
            for employee in active_employees
            if employee.id not in submitted_user_ids
        ]

        return FeasibilitySummary(
            total_slots=total_slots,
            active_employee_count=active_employee_count,
            avg_shifts_per_employee=avg_shifts_per_employee,
            min_shifts_per_month=min_shifts_per_month,
            max_weekend_shifts=max_weekend_shifts,
            weekend_slot_count=weekend_slot_count,
            total_declared=total_declared,
            min_shifts_feasible=min_shifts_feasible,
            availability_feasible=availability_feasible,
            weekend_feasible=weekend_feasible,
            not_submitted=not_submitted,
        )
