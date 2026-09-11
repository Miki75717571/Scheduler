import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability import Availability, AvailabilityStatus, AvailabilitySubmission


class AvailabilityRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_submission(
        self, user_id: uuid.UUID, period_id: uuid.UUID
    ) -> AvailabilitySubmission | None:
        result = await self._db.execute(
            select(AvailabilitySubmission).where(
                AvailabilitySubmission.user_id == user_id,
                AvailabilitySubmission.period_id == period_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_submissions_for_period(
        self, period_id: uuid.UUID
    ) -> list[AvailabilitySubmission]:
        result = await self._db.execute(
            select(AvailabilitySubmission).where(AvailabilitySubmission.period_id == period_id)
        )
        return list(result.scalars())

    async def create_submission(self, submission: AvailabilitySubmission) -> AvailabilitySubmission:
        self._db.add(submission)
        await self._db.flush()
        return submission

    async def save_submission(self, submission: AvailabilitySubmission) -> AvailabilitySubmission:
        await self._db.flush()
        return submission

    async def list_entries(self, submission_id: uuid.UUID) -> list[Availability]:
        result = await self._db.execute(
            select(Availability).where(Availability.submission_id == submission_id)
        )
        return list(result.scalars())

    async def get_entry(
        self, submission_id: uuid.UUID, shift_slot_id: uuid.UUID
    ) -> Availability | None:
        result = await self._db.execute(
            select(Availability).where(
                Availability.submission_id == submission_id,
                Availability.shift_slot_id == shift_slot_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_entry(
        self,
        submission_id: uuid.UUID,
        shift_slot_id: uuid.UUID,
        status: AvailabilityStatus,
        note: str | None,
    ) -> None:
        entry = await self.get_entry(submission_id, shift_slot_id)
        if entry is None:
            self._db.add(
                Availability(
                    submission_id=submission_id,
                    shift_slot_id=shift_slot_id,
                    status=status,
                    note=note,
                )
            )
        else:
            entry.status = status
            entry.note = note
        await self._db.flush()

    async def delete_entry(self, submission_id: uuid.UUID, shift_slot_id: uuid.UUID) -> None:
        await self._db.execute(
            delete(Availability).where(
                Availability.submission_id == submission_id,
                Availability.shift_slot_id == shift_slot_id,
            )
        )
