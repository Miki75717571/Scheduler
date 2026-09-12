import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Integer, String, func, true
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.types import StrEnumType, UTCDateTime


class Role(enum.StrEnum):
    EMPLOYEE = "EMPLOYEE"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"


class EmploymentType(enum.StrEnum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    STUDENT = "STUDENT"
    CASUAL = "CASUAL"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('EMPLOYEE','MANAGER','ADMIN')", name="ck_users_role"),
        CheckConstraint(
            "employment_type IN ('FULL_TIME','PART_TIME','STUDENT','CASUAL')"
            " OR employment_type IS NULL",
            name="ck_users_employment_type",
        ),
    )

    # Uuid (generic): native UUID on Postgres, portable string storage on
    # SQLite/others. Generated app-side (not server_default=gen_random_uuid(),
    # which is Postgres-only) so it works identically on every dialect.
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # StrEnumType + CheckConstraint above: portable String storage (see
    # app/db/types.py) instead of a native Postgres ENUM, which SQLite can't
    # represent at all.
    role: Mapped[Role] = mapped_column(StrEnumType(Role, 20), nullable=False)
    # Nullable: invitations (see Invitation below) don't carry employment_type, so it's
    # unset until an admin fills it in via PATCH /users/{id}.
    employment_type: Mapped[EmploymentType | None] = mapped_column(
        StrEnumType(EmploymentType, 20), nullable=True
    )
    contract_min_shifts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contract_max_shifts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # ARCHITECTURE.md ss4.2: +1 when a PREFERRED slot is denied by a solver
    # run, -1 when granted - carried across months so the objective can
    # correct for a run of bad luck (app/services/solver_service.py's
    # `_apply_preference_debt`). Never shown to employees (same never-see-
    # your-own-score rule as EmployeeScore, ARCHITECTURE.md ss5).
    preference_debt: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    locale: Mapped[str] = mapped_column(
        String(5), nullable=False, default="pl", server_default="pl"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, server_default=func.now()
    )
    invited_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
