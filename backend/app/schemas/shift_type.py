import uuid
from datetime import time

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.rules.weekdays import Weekday


class ShiftTypeWeekdayOverrideRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shift_type_id: uuid.UUID
    weekday: Weekday
    start_time: time
    end_time: time
    min_staff: int
    required_staff: int
    max_staff: int


class ShiftTypeWeekdayOverrideWrite(BaseModel):
    start_time: time
    end_time: time
    min_staff: int = Field(ge=0)
    required_staff: int = Field(ge=0)
    max_staff: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_ranges(self) -> "ShiftTypeWeekdayOverrideWrite":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if not (self.min_staff <= self.required_staff <= self.max_staff):
            raise ValueError("min_staff <= required_staff <= max_staff")
        return self


class ShiftTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name_pl: str
    name_en: str
    start_time: time
    end_time: time
    color_hex: str
    active_weekdays: int
    default_required_staff: int
    default_min_staff: int
    default_max_staff: int
    sort_order: int
    is_active: bool
    overrides: list[ShiftTypeWeekdayOverrideRead] = Field(default_factory=list)


class ShiftTypeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name_pl: str = Field(min_length=1)
    name_en: str = Field(min_length=1)
    start_time: time
    end_time: time
    color_hex: str = "#64748b"
    active_weekdays: int = Field(gt=0, le=127)
    default_required_staff: int = Field(ge=0)
    default_min_staff: int = Field(ge=0)
    default_max_staff: int = Field(ge=0)
    sort_order: int = 0

    @model_validator(mode="after")
    def _check_time_order(self) -> "ShiftTypeCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class ShiftTypeUpdate(BaseModel):
    name_pl: str | None = None
    name_en: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    color_hex: str | None = None
    active_weekdays: int | None = Field(default=None, gt=0, le=127)
    default_required_staff: int | None = Field(default=None, ge=0)
    default_min_staff: int | None = Field(default=None, ge=0)
    default_max_staff: int | None = Field(default=None, ge=0)
    sort_order: int | None = None
    is_active: bool | None = None
