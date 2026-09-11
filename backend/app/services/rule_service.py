import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rule import Rule
from app.repositories.rule_repository import RuleRepository
from app.rules.params import RuleParamsError, validate_rule_params
from app.schemas.rule import RuleCreate, RuleUpdate


class RuleError(Exception):
    def __init__(self, message_key: str, params: dict[str, Any] | None = None) -> None:
        self.message_key = message_key
        self.params = params or {}
        super().__init__(message_key)


class RuleService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = RuleRepository(db)

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
