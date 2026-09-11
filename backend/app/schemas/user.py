import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import EmploymentType, Role


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


class UserAdminUpdate(BaseModel):
    """Fields only an admin may edit, and only about someone else's account."""

    full_name: str | None = None
    phone: str | None = None
    role: Role | None = None
    employment_type: EmploymentType | None = None
    contract_min_shifts: int | None = None
    contract_max_shifts: int | None = None
    is_active: bool | None = None
