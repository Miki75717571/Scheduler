import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.rule import RulePhase, RuleScope, RuleSeverity, RuleType


class RuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name_pl: str
    name_en: str
    type: RuleType
    scope: RuleScope
    scope_ref: str | None
    params: dict[str, Any]
    severity: RuleSeverity
    weight: int | None
    phase: RulePhase
    is_active: bool


class RuleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    name_pl: str = Field(min_length=1)
    name_en: str = Field(min_length=1)
    type: RuleType
    scope: RuleScope = RuleScope.GLOBAL
    scope_ref: str | None = None
    params: dict[str, Any]
    severity: RuleSeverity = RuleSeverity.HARD
    weight: int | None = None
    phase: RulePhase = RulePhase.AVAILABILITY
    is_active: bool = True


class RuleUpdate(BaseModel):
    name_pl: str | None = None
    name_en: str | None = None
    params: dict[str, Any] | None = None
    severity: RuleSeverity | None = None
    weight: int | None = None
    is_active: bool | None = None


class RestConflictRead(BaseModel):
    from_shift_type_code: str
    from_weekday: str
    to_shift_type_code: str
    to_weekday: str
    gap_hours: float
    required_hours: int
