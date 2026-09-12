import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ScoreCriterionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name_pl: str
    name_en: str
    description: str | None
    weight: Decimal
    scale_min: int
    scale_max: int
    is_active: bool


class ScoreCriterionCreate(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    name_pl: str = Field(min_length=1)
    name_en: str = Field(min_length=1)
    description: str | None = None
    weight: Decimal = Field(default=Decimal("0"), ge=0)
    # Starts inactive by default: an admin adding a new criterion almost
    # always needs to rebalance every other active weight in the same
    # transaction (see ScoreWeightsUpdate below) - creating it active would
    # near-guarantee an immediate "weights must sum to 1.0" rejection.
    is_active: bool = False


class ScoreCriterionUpdate(BaseModel):
    """Renaming/describing never touches the weight-sum invariant, so those
    fields can always be saved standalone. `weight`/`is_active` are accepted
    too (for the trivial single-row case, e.g. the only active criterion), but
    coordinated multi-row rebalancing should go through ScoreWeightsUpdate
    instead - see app/services/score_service.py.
    """

    name_pl: str | None = None
    name_en: str | None = None
    description: str | None = None
    weight: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ScoreWeightsUpdateItem(BaseModel):
    id: uuid.UUID
    weight: Decimal = Field(ge=0)
    is_active: bool


class ScoreWeightsUpdate(BaseModel):
    """Applies several criteria's weight/is_active together in one
    transaction, checked as a whole against the "active weights sum to
    exactly 1.0" rule - the only way to move from one valid weight
    distribution to another without an invalid state in between.
    """

    items: list[ScoreWeightsUpdateItem] = Field(min_length=1)
