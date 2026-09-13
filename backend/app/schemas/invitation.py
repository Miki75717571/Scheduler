import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import Role

InvitationStatus = Literal["PENDING", "ACCEPTED", "EXPIRED", "REVOKED"]


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
    revoked_at: datetime | None
    status: InvitationStatus
    # Only populated when the configured email provider can't actually
    # deliver the invite itself ("console") - see
    # tests/api/test_invitations.py::test_accept_url_is_absent_when_using_resend.
    # The token is hashed at rest specifically so it can't be recovered from
    # the DB; it must not leak back out through the API when email delivery
    # is real either.
    accept_url: str | None = None


class InvitationPreview(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    role: Role
    expires_at: datetime


class InvitationAccept(BaseModel):
    token: str
    full_name: str = Field(min_length=1)
    password: str = Field(min_length=8)
