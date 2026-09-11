import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import EmploymentType, Role


def _blank_string_to_none(value: Any) -> Any:
    """An empty string from an optional form field means "no value" / "no
    change", not a literal empty value - e.g. the Profile screen always sends
    `phone` and `password`, blank or not. Without this, an untouched blank
    password field 422s against the min_length check instead of being treated
    as "don't change the password".
    """
    if isinstance(value, str) and value == "":
        return None
    return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    phone: str | None
    role: Role
    employment_type: EmploymentType | None
    contract_min_shifts: int | None
    contract_max_shifts: int | None
    locale: str
    is_active: bool
    created_at: datetime
    invited_at: datetime | None
    activated_at: datetime | None


class UserUpdate(BaseModel):
    """Fields an employee may edit about themselves."""

    full_name: str | None = None
    phone: str | None = None
    locale: str | None = None
    password: str | None = Field(default=None, min_length=8)

    _normalize_phone = field_validator("phone", mode="before")(_blank_string_to_none)
    _normalize_password = field_validator("password", mode="before")(_blank_string_to_none)


class UserAdminUpdate(BaseModel):
    """Fields only an admin may edit, and only about someone else's account."""

    full_name: str | None = None
    phone: str | None = None
    role: Role | None = None
    employment_type: EmploymentType | None = None
    contract_min_shifts: int | None = None
    contract_max_shifts: int | None = None
    is_active: bool | None = None

    _normalize_phone = field_validator("phone", mode="before")(_blank_string_to_none)
