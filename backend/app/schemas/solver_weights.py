import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SolverWeightsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    understaffing: int
    contract_min_shortfall: int
    denied_preference: int
    fairness_spread: int
    unpopular_shift_spread: int
    score_weight: int
    preference_debt: int
    updated_at: datetime | None
    updated_by_user_id: uuid.UUID | None


class SolverWeightsUpdate(BaseModel):
    """All-or-nothing update, like ScoreWeightsUpdate - there's no meaningful
    "just tweak one field" for an objective whose terms all trade off against
    each other (ARCHITECTURE.md ss4.1).
    """

    understaffing: int = Field(ge=0, le=1_000_000)
    contract_min_shortfall: int = Field(ge=0, le=1_000_000)
    denied_preference: int = Field(ge=0, le=1_000_000)
    fairness_spread: int = Field(ge=0, le=1_000_000)
    unpopular_shift_spread: int = Field(ge=0, le=1_000_000)
    score_weight: int = Field(ge=0, le=1_000_000)
    preference_debt: int = Field(ge=0, le=1_000_000)
