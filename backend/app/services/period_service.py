import calendar
import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability import AvailabilitySubmission, SubmissionStatus
from app.models.schedule_period import PeriodState, SchedulePeriod
from app.models.shift_slot import ShiftSlot
from app.models.shift_type import ShiftType
from app.models.user import User
from app.repositories.availability_repository import AvailabilityRepository
from app.repositories.period_repository import PeriodRepository
from app.repositories.shift_slot_repository import ShiftSlotRepository
from app.repositories.shift_type_repository import ShiftTypeRepository
from app.repositories.user_repository import UserRepository
from app.rules.weekdays import active_on
from app.schemas.period import PeriodCreate
from app.schemas.shift_slot import ShiftSlotUpdate


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


def _generate_slots(period: SchedulePeriod, shift_types: list[ShiftType]) -> list[ShiftSlot]:
    days_in_month = calendar.monthrange(period.year, period.month)[1]
    slots: list[ShiftSlot] = []
    for day in range(1, days_in_month + 1):
        current = date(period.year, period.month, day)
        for shift_type in shift_types:
            if not active_on(shift_type.active_weekdays, current):
                continue
            slots.append(
                ShiftSlot(
                    period_id=period.id,
                    date=current,
                    shift_type_id=shift_type.id,
                    required_staff=shift_type.default_required_staff,
                    min_staff=shift_type.default_min_staff,
                    max_staff=shift_type.default_max_staff,
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
        slots = _generate_slots(period, shift_types)
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
        self, period: SchedulePeriod, target: PeriodState, *, actor: User
    ) -> SchedulePeriod:
        expected_next = _LEGAL_TRANSITIONS.get(period.state)
        if expected_next != target:
            raise PeriodError(
                "period.illegal_transition", {"from": period.state.value, "to": target.value}
            )

        period.state = target
        if target == PeriodState.COLLECTING:
            await self._ensure_submissions_for_active_users(period)
        elif target == PeriodState.PUBLISHED:
            period.published_at = datetime.now(UTC)
            period.published_by_user_id = actor.id

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

    async def update_slot(
        self, period: SchedulePeriod, slot_id: uuid.UUID, payload: ShiftSlotUpdate
    ) -> ShiftSlot:
        slot = await self._slots.get_by_id(slot_id)
        if slot is None or slot.period_id != period.id:
            raise PeriodError("shift_slot.not_found")

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(slot, field, value)
        if not (slot.min_staff <= slot.required_staff <= slot.max_staff):
            raise PeriodError("shift_slot.invalid_staff_levels")

        await self._slots.save(slot)
        await self._db.commit()
        await self._db.refresh(slot)
        return slot
