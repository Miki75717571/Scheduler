import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rule import Rule, RulePhase, RuleType
from app.repositories.rule_repository import RuleRepository
from app.repositories.shift_type_repository import ShiftTypeRepository
from app.rules.params import RuleParamsError, validate_rule_params
from app.rules.rest_conflicts import RestConflict, ShiftOccurrence, find_impossible_adjacent_pairs
from app.rules.weekdays import active_on, weekday_of
from app.schemas.rule import RuleCreate, RuleUpdate
from app.services.shift_effective import overrides_by_weekday_for, resolve_effective_config

# An arbitrary Monday - only used to walk one representative week of
# weekdays (Weekday.MON..SUN), never a real schedule date.
_REFERENCE_MONDAY = date(2024, 1, 1)


class RuleError(Exception):
    def __init__(self, message_key: str, params: dict[str, Any] | None = None) -> None:
        self.message_key = message_key
        self.params = params or {}
        super().__init__(message_key)


class RuleService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = RuleRepository(db)
        self._shift_types = ShiftTypeRepository(db)

    async def list_all(self) -> list[Rule]:
        return await self._repo.list_all()

    async def create(self, payload: RuleCreate) -> Rule:
        if await self._repo.get_by_code(payload.code) is not None:
            raise RuleError("rule.code_already_exists")
        try:
            validate_rule_params(payload.type, payload.params)
        except RuleParamsError as exc:
            raise RuleError(exc.message_key, exc.params) from exc

        rule = Rule(**payload.model_dump())
        await self._repo.create(rule)
        await self._db.commit()
        await self._db.refresh(rule)
        return rule

    async def update(self, rule_id: uuid.UUID, payload: RuleUpdate) -> Rule:
        rule = await self._repo.get_by_id(rule_id)
        if rule is None:
            raise RuleError("rule.not_found")

        updates = payload.model_dump(exclude_unset=True)
        if "params" in updates:
            try:
                validate_rule_params(rule.type, updates["params"])
            except RuleParamsError as exc:
                raise RuleError(exc.message_key, exc.params) from exc

        for field, value in updates.items():
            setattr(rule, field, value)

        await self._repo.save(rule)
        await self._db.commit()
        await self._db.refresh(rule)
        return rule

    # --- rest-rule conflict detection (CLAUDE.md JOB 4) --------------------

    async def rest_conflicts(self) -> list[RestConflict]:
        """Runs app/rules/rest_conflicts.py against the LIVE shift
        configuration and the strictest currently-active MIN_REST_HOURS
        value, so the admin rules screen can warn "MIN_REST_HOURS=11 makes
        Friday EVENING -> Saturday MORNING impossible" immediately, before a
        manager ever runs the solver.
        """
        schedule_rules = await self._repo.list_active_by_phase(RulePhase.SCHEDULE)
        rest_rules = [r for r in schedule_rules if r.type == RuleType.MIN_REST_HOURS]
        if not rest_rules:
            return []
        min_rest_hours = max(int(r.params["h"]) for r in rest_rules)

        shift_types = await self._shift_types.list_all(active_only=True)
        overrides = await self._shift_types.list_overrides_for_types([st.id for st in shift_types])
        overrides_by_type: dict[uuid.UUID, list[Any]] = {}
        for override in overrides:
            overrides_by_type.setdefault(override.shift_type_id, []).append(override)

        occurrences: list[ShiftOccurrence] = []
        for shift_type in shift_types:
            overrides_by_weekday = overrides_by_weekday_for(
                overrides_by_type.get(shift_type.id, [])
            )
            for offset in range(7):
                day = _REFERENCE_MONDAY + timedelta(days=offset)
                if not active_on(shift_type.active_weekdays, day):
                    continue
                effective = resolve_effective_config(shift_type, overrides_by_weekday, day)
                occurrences.append(
                    ShiftOccurrence(
                        shift_type_code=shift_type.code,
                        weekday=weekday_of(day),
                        start_time=effective.start_time,
                        end_time=effective.end_time,
                    )
                )

        return find_impossible_adjacent_pairs(occurrences, min_rest_hours)
