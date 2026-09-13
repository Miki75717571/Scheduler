"""per-weekday shift type overrides

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-13

Adds `shift_type_weekday_overrides`: a per-(shift_type, weekday) override of
start_time/end_time/min_staff/required_staff/max_staff, so one ShiftType code
(e.g. "EVENING") can mean 14:00-20:00 on Mon-Thu, 15:00-22:00 on Friday, and
14:00-20:00 again on Sat/Sun - see app/services/shift_effective.py. ShiftType
itself keeps its own start_time/end_time/staff triple as the fallback for any
active weekday without an override row. Portable across SQLite/Postgres per
CLAUDE.md: plain VARCHAR + CHECK for the weekday enum, every constraint
declared inline in create_table().
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shift_type_weekday_overrides",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("shift_type_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("weekday", sa.String(length=3), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("min_staff", sa.Integer(), nullable=False),
        sa.Column("required_staff", sa.Integer(), nullable=False),
        sa.Column("max_staff", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["shift_type_id"], ["shift_types.id"]),
        sa.UniqueConstraint(
            "shift_type_id", "weekday", name="uq_shift_type_weekday_overrides_type_day"
        ),
        sa.CheckConstraint(
            "end_time > start_time", name="ck_shift_type_weekday_overrides_time_order"
        ),
        sa.CheckConstraint(
            "min_staff <= required_staff AND required_staff <= max_staff",
            name="ck_shift_type_weekday_overrides_staff_order",
        ),
        sa.CheckConstraint(
            "weekday IN ('MON','TUE','WED','THU','FRI','SAT','SUN')",
            name="ck_shift_type_weekday_overrides_weekday",
        ),
    )
    op.create_index(
        "ix_shift_type_weekday_overrides_shift_type_id",
        "shift_type_weekday_overrides",
        ["shift_type_id"],
    )


def downgrade() -> None:
    op.drop_table("shift_type_weekday_overrides")
