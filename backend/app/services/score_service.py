import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee_score import EmployeeScore
from app.models.score_criterion import ScoreCriterion
from app.models.user import User
from app.repositories.employee_score_repository import EmployeeScoreRepository
from app.repositories.score_criterion_repository import ScoreCriterionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.employee_score import (
    EmployeeScoreCreate,
    ScoreEntryRead,
    ScoreGridRow,
    ScoreHistoryEntryRead,
)
from app.schemas.score_criterion import (
    ScoreCriterionCreate,
    ScoreCriterionUpdate,
    ScoreWeightsUpdate,
)


class ScoreError(Exception):
    def __init__(self, message_key: str, params: dict[str, Any] | None = None) -> None:
        self.message_key = message_key
        self.params = params or {}
        super().__init__(message_key)


def _validate_active_weights_sum(criteria: list[ScoreCriterion]) -> None:
    active = [c for c in criteria if c.is_active]
    if not active:
        return  # nothing configured yet - not an error, just "no composite available"
    total = sum((c.weight for c in active), Decimal("0"))
    if total != Decimal("1"):
        raise ScoreError("score_criterion.weights_must_sum_to_one", {"total": str(total)})


def _composite(
    entries_by_criterion_id: dict[uuid.UUID, EmployeeScore], active_criteria: list[ScoreCriterion]
) -> float | None:
    """ARCHITECTURE.md ss3.4: 100 * sum(weight * (value-1)/(scale_max-1)).
    None (not a partial score) unless every active criterion has a current
    value for this employee - a partial sum would silently renormalize the
    weights of whatever happened to be rated, which is misleading.
    """
    if not active_criteria:
        return None
    total = Decimal("0")
    for criterion in active_criteria:
        entry = entries_by_criterion_id.get(criterion.id)
        if entry is None:
            return None
        span = Decimal(criterion.scale_max - criterion.scale_min)
        total += criterion.weight * (Decimal(entry.value - criterion.scale_min) / span)
    return float((total * 100).quantize(Decimal("0.1")))


class ScoreService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._criteria = ScoreCriterionRepository(db)
        self._scores = EmployeeScoreRepository(db)
        self._users = UserRepository(db)

    # --- criteria (admin) ----------------------------------------------

    async def list_criteria(self, *, active_only: bool = False) -> list[ScoreCriterion]:
        return await self._criteria.list_all(active_only=active_only)

    async def create_criterion(self, payload: ScoreCriterionCreate) -> ScoreCriterion:
        if await self._criteria.get_by_code(payload.code) is not None:
            raise ScoreError("score_criterion.code_already_exists")

        criterion = ScoreCriterion(**payload.model_dump())
        if criterion.is_active:
            others = await self._criteria.list_all()
            _validate_active_weights_sum([*others, criterion])

        await self._criteria.create(criterion)
        await self._db.commit()
        await self._db.refresh(criterion)
        return criterion

    async def update_criterion(
        self, criterion_id: uuid.UUID, payload: ScoreCriterionUpdate
    ) -> ScoreCriterion:
        criterion = await self._criteria.get_by_id(criterion_id)
        if criterion is None:
            raise ScoreError("score_criterion.not_found")

        updates = payload.model_dump(exclude_unset=True)
        touches_weight = "weight" in updates or "is_active" in updates
        for field, value in updates.items():
            setattr(criterion, field, value)

        if touches_weight:
            others = [c for c in await self._criteria.list_all() if c.id != criterion.id]
            _validate_active_weights_sum([*others, criterion])

        await self._criteria.save(criterion)
        await self._db.commit()
        await self._db.refresh(criterion)
        return criterion

    async def deactivate_criterion(self, criterion_id: uuid.UUID) -> ScoreCriterion:
        criterion = await self._criteria.get_by_id(criterion_id)
        if criterion is None:
            raise ScoreError("score_criterion.not_found")

        criterion.is_active = False
        others = [c for c in await self._criteria.list_all() if c.id != criterion.id]
        _validate_active_weights_sum([*others, criterion])

        await self._criteria.save(criterion)
        await self._db.commit()
        await self._db.refresh(criterion)
        return criterion

    async def update_weights(self, payload: ScoreWeightsUpdate) -> list[ScoreCriterion]:
        """Applies every item together, validated as one resulting state -
        see ScoreWeightsUpdate's docstring for why this can't be several
        independent single-row saves.
        """
        all_criteria = await self._criteria.list_all()
        by_id = {c.id: c for c in all_criteria}
        for item in payload.items:
            if item.id not in by_id:
                raise ScoreError("score_criterion.not_found")

        for item in payload.items:
            criterion = by_id[item.id]
            criterion.weight = item.weight
            criterion.is_active = item.is_active

        _validate_active_weights_sum(all_criteria)

        await self._db.commit()
        touched = [by_id[item.id] for item in payload.items]
        for criterion in touched:
            await self._db.refresh(criterion)
        return touched

    # --- scores (manager/admin) -----------------------------------------

    async def set_score(
        self, *, user_id: uuid.UUID, payload: EmployeeScoreCreate, actor: User
    ) -> EmployeeScore:
        target = await self._users.get_by_id(user_id)
        if target is None:
            raise ScoreError("score.user_not_found")

        criterion = await self._criteria.get_by_id(payload.criterion_id)
        if criterion is None:
            raise ScoreError("score.criterion_not_found")
        if not criterion.is_active:
            raise ScoreError("score.criterion_inactive")

        score = EmployeeScore(
            user_id=target.id,
            criterion_id=criterion.id,
            value=payload.value,
            effective_from=payload.effective_from or date.today(),
            set_by_user_id=actor.id,
            note=payload.note,
        )
        await self._scores.create(score)
        await self._db.commit()
        await self._db.refresh(score)
        return score

    async def get_grid(self, users: list[User], *, as_of: date | None = None) -> list[ScoreGridRow]:
        as_of = as_of or date.today()
        active_criteria = await self._criteria.list_all(active_only=True)
        rows = await self._scores.list_effective_rows({u.id for u in users}, as_of=as_of)

        effective: dict[uuid.UUID, dict[uuid.UUID, EmployeeScore]] = defaultdict(dict)
        for row in rows:
            # Rows come back latest-first per (user, criterion) - keep only
            # the first one seen for each pair.
            per_user = effective[row.user_id]
            if row.criterion_id not in per_user:
                per_user[row.criterion_id] = row

        grid: list[ScoreGridRow] = []
        for user in users:
            entries_by_id = effective.get(user.id, {})
            entries = [
                ScoreEntryRead(
                    criterion_id=criterion.id,
                    value=entries_by_id[criterion.id].value,
                    effective_from=entries_by_id[criterion.id].effective_from,
                    set_by_user_id=entries_by_id[criterion.id].set_by_user_id,
                    note=entries_by_id[criterion.id].note,
                )
                for criterion in active_criteria
                if criterion.id in entries_by_id
            ]
            grid.append(
                ScoreGridRow(
                    user_id=user.id,
                    full_name=user.full_name,
                    entries=entries,
                    composite=_composite(entries_by_id, active_criteria),
                )
            )
        return grid

    async def get_history(self, user_id: uuid.UUID) -> list[ScoreHistoryEntryRead]:
        target = await self._users.get_by_id(user_id)
        if target is None:
            raise ScoreError("score.user_not_found")

        rows = await self._scores.list_history_for_user(user_id)
        criteria_by_id = {
            c.id: c for c in await self._criteria.list_by_ids({r.criterion_id for r in rows})
        }
        setters_by_id = {
            u.id: u for u in await self._users.list_by_ids({r.set_by_user_id for r in rows})
        }

        rows_by_criterion: dict[uuid.UUID, list[EmployeeScore]] = defaultdict(list)
        for row in rows:
            rows_by_criterion[row.criterion_id].append(row)

        history: list[ScoreHistoryEntryRead] = []
        for criterion_id, group in rows_by_criterion.items():
            criterion = criteria_by_id.get(criterion_id)
            if criterion is None:
                continue  # defensive only - criteria are deactivated, never deleted
            for index, row in enumerate(group):
                previous = group[index + 1] if index + 1 < len(group) else None
                setter = setters_by_id.get(row.set_by_user_id)
                history.append(
                    ScoreHistoryEntryRead(
                        id=row.id,
                        criterion_id=criterion.id,
                        criterion_code=criterion.code,
                        criterion_name_pl=criterion.name_pl,
                        criterion_name_en=criterion.name_en,
                        value=row.value,
                        previous_value=previous.value if previous is not None else None,
                        effective_from=row.effective_from,
                        set_by_user_id=row.set_by_user_id,
                        set_by_full_name=setter.full_name if setter is not None else "",
                        note=row.note,
                        created_at=row.created_at,
                    )
                )

        history.sort(key=lambda h: (h.effective_from, h.created_at), reverse=True)
        return history
