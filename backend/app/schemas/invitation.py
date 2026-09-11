import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import Role


class InvitationCreate(BaseModel):
    email: EmailStr
    role: Role


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: Role
    expires_at: datetime
    accepted_at: datetime | None


class InvitationPreview(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    role: Role
    expires_at: datetime


class InvitationAccept(BaseModel):
    token: str
    full_name: str = Field(min_length=1)
    password: str = Field(min_length=8)
