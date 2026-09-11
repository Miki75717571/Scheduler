import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability import (
    Availability,
    AvailabilityStatus,
    AvailabilitySubmission,
    SubmissionStatus,
)
from app.models.rule import RulePhase, RuleSeverity
from app.models.schedule_period import PeriodState, SchedulePeriod
from app.models.user import User
from app.repositories.availability_repository import AvailabilityRepository
from app.repositories.rule_repository import RuleRepository
from app.repositories.shift_slot_repository import ShiftSlotRepository
from app.repositories.shift_type_repository import ShiftTypeRepository
from app.rules.availability_validator import evaluate_availability_rules
from app.rules.types import RuleCheckResult, SlotContext
from app.schemas.availability import AvailabilityEntryWrite


class AvailabilityError(Exception):
    def __init__(self, message_key: str, params: dict[str, Any] | None = None) -> None:
        self.message_key = message_key
        self.params = params or {}
        super().__init__(message_key)


class AvailabilityService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._availability = AvailabilityRepository(db)
        self._slots = ShiftSlotRepository(db)
        self._shift_types = ShiftTypeRepository(db)
        self._rules = RuleRepository(db)

    async def _get_or_create_submission(
        self, user_id: uuid.UUID, period: SchedulePeriod
    ) -> AvailabilitySubmission:
        submission = await self._availability.get_submission(user_id, period.id)
        if submission is None:
            submission = await self._availability.create_submission(
                AvailabilitySubmission(
                    user_id=user_id, period_id=period.id, status=SubmissionStatus.NOT_STARTED
                )
            )
        return submission

    def _assert_can_write(self, period: SchedulePeriod, submission: AvailabilitySubmission) -> None:
        if period.state == PeriodState.COLLECTING:
            return
        if period.state == PeriodState.LOCKED and submission.reopened_by_manager:
            return
        raise AvailabilityError("availability.period_not_editable", {"state": period.state.value})

    async def get_detail(
        self, *, user: User, period: SchedulePeriod
    ) -> tuple[AvailabilitySubmission, list[Availability], list[RuleCheckResult]]:
        submission = await self._get_or_create_submission(user.id, period)
        entries = await self._availability.list_entries(submission.id)
        validation = await self._validate(user=user, submission=submission)
        return submission, entries, validation

    async def write(
        self, *, user: User, period: SchedulePeriod, entries: list[AvailabilityEntryWrite]
    ) -> AvailabilitySubmission:
        submission = await self._get_or_create_submission(user.id, period)
        self._assert_can_write(period, submission)

        slot_ids = {e.shift_slot_id for e in entries}
        slots = {s.id: s for s in await self._slots.get_many(slot_ids)}
        for entry in entries:
            slot = slots.get(entry.shift_slot_id)
            if slot is None or slot.period_id != period.id:
                raise AvailabilityError("availability.invalid_shift_slot")
            if entry.status == AvailabilityStatus.UNAVAILABLE:
                await self._availability.delete_entry(submission.id, entry.shift_slot_id)
            else:
                await self._availability.upsert_entry(
                    submission.id, entry.shift_slot_id, entry.status, entry.note
                )

        submission.status = SubmissionStatus.DRAFT
        submission.last_edited_at = datetime.now(UTC)
        await self._availability.save_submission(submission)
        await self._db.commit()
        await self._db.refresh(submission)
        return submission

    async def submit(
        self, *, user: User, period: SchedulePeriod
    ) -> tuple[AvailabilitySubmission, list[RuleCheckResult]]:
        submission = await self._get_or_create_submission(user.id, period)
        self._assert_can_write(period, submission)

        validation = await self._validate(user=user, submission=submission)
        hard_failures = [
            r for r in validation if r.severity == RuleSeverity.HARD.value and not r.passed
        ]
        if hard_failures:
            raise AvailabilityError(
                "availability.hard_rules_failed", {"rules": [r.rule_code for r in hard_failures]}
            )

        submission.status = SubmissionStatus.SUBMITTED
        submission.submitted_at = datetime.now(UTC)
        await self._availability.save_submission(submission)
        await self._db.commit()
        await self._db.refresh(submission)
        return submission, validation

    async def reopen(
        self, *, period: SchedulePeriod, user_id: uuid.UUID, reopened: bool
    ) -> AvailabilitySubmission:
        if period.state != PeriodState.LOCKED:
            raise AvailabilityError("availability.reopen_requires_locked_period")

        submission = await self._get_or_create_submission(user_id, period)
        submission.reopened_by_manager = reopened
        await self._availability.save_submission(submission)
        await self._db.commit()
        await self._db.refresh(submission)
        return submission

    async def _validate(
        self, *, user: User, submission: AvailabilitySubmission
    ) -> list[RuleCheckResult]:
        entries = await self._availability.list_entries(submission.id)
        slot_ids = {e.shift_slot_id for e in entries}
        slots = {s.id: s for s in await self._slots.get_many(slot_ids)}
        shift_types = {st.id: st for st in await self._shift_types.list_all()}

        contexts = [
            SlotContext(
                shift_slot_id=e.shift_slot_id,
                date=slots[e.shift_slot_id].date,
                shift_type_code=shift_types[slots[e.shift_slot_id].shift_type_id].code,
                status=e.status,
            )
            for e in entries
            if e.shift_slot_id in slots
        ]
        rules = await self._rules.list_applicable(
            phase=RulePhase.AVAILABILITY, user_id=user.id, employment_type=user.employment_type
        )
        return evaluate_availability_rules(rules, contexts)

    async def list_submission_tracker(
        self, *, period: SchedulePeriod, users: list[User]
    ) -> list[tuple[User, AvailabilitySubmission | None]]:
        submissions = await self._availability.list_submissions_for_period(period.id)
        by_user = {s.user_id: s for s in submissions}
        return [(u, by_user.get(u.id)) for u in users]
