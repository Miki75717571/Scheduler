import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rule import Rule, RulePhase, RuleScope
from app.models.user import EmploymentType


class RuleRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, rule_id: uuid.UUID) -> Rule | None:
        return await self._db.get(Rule, rule_id)

    async def get_by_code(self, code: str) -> Rule | None:
        result = await self._db.execute(select(Rule).where(Rule.code == code))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Rule]:
        result = await self._db.execute(select(Rule).order_by(Rule.code))
        return list(result.scalars())

    async def create(self, rule: Rule) -> Rule:
        self._db.add(rule)
        await self._db.flush()
        return rule

    async def save(self, rule: Rule) -> Rule:
        await self._db.flush()
        return rule

    async def list_applicable(
        self,
        *,
        phase: RulePhase,
        user_id: uuid.UUID,
        employment_type: EmploymentType | None,
    ) -> list[Rule]:
        """Rules that apply to this user right now: GLOBAL, plus their
        EMPLOYMENT_TYPE (if set), plus any USER-scoped rule addressed to
        them specifically - restricted to this phase (or BOTH), active only.
        """
        stmt = select(Rule).where(
            Rule.is_active.is_(True),
            (Rule.phase == phase) | (Rule.phase == RulePhase.BOTH),
            or_(
                Rule.scope == RuleScope.GLOBAL,
                (Rule.scope == RuleScope.USER) & (Rule.scope_ref == str(user_id)),
                *(
                    [
                        (Rule.scope == RuleScope.EMPLOYMENT_TYPE)
                        & (Rule.scope_ref == employment_type.value)
                    ]
                    if employment_type is not None
                    else []
                ),
            ),
        )
        result = await self._db.execute(stmt)
        return list(result.scalars())
