"""create users and invitations tables

Revision ID: 0001
Revises:
Create Date: 2026-09-10

Portable across SQLite and Postgres: roles/employment types are plain
VARCHAR + CHECK constraints (not a native Postgres ENUM, which SQLite has no
equivalent for - see app/db/types.py), ids are sa.Uuid (native UUID on
Postgres, portable string storage elsewhere) generated app-side rather than
via Postgres's gen_random_uuid(), and every constraint is declared inline in
create_table() rather than added after with a separate ALTER TABLE (which
SQLite mostly can't do outside Alembic's batch mode).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("employment_type", sa.String(length=20), nullable=True),
        sa.Column("contract_min_shifts", sa.Integer(), nullable=True),
        sa.Column("contract_max_shifts", sa.Integer(), nullable=True),
        sa.Column("locale", sa.String(length=5), nullable=False, server_default="pl"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint("role IN ('EMPLOYEE','MANAGER','ADMIN')", name="ck_users_role"),
        sa.CheckConstraint(
            "employment_type IN ('FULL_TIME','PART_TIME','STUDENT','CASUAL')"
            " OR employment_type IS NULL",
            name="ck_users_employment_type",
        ),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("token_hash", name="uq_invitations_token_hash"),
        sa.CheckConstraint("role IN ('EMPLOYEE','MANAGER','ADMIN')", name="ck_invitations_role"),
    )
    op.create_index("ix_invitations_email", "invitations", ["email"])


def downgrade() -> None:
    op.drop_table("invitations")
    op.drop_table("users")
