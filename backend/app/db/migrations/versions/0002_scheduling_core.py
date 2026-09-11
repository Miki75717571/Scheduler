"""create scheduling core tables (shift types, periods, slots, availability, rules)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-11

Portable across SQLite and Postgres, following the same conventions as 0001:
plain VARCHAR + CHECK constraints instead of a native ENUM, sa.Uuid ids
generated app-side, sa.JSON (not JSONB) for Rule.params, sa.Time/sa.Date for
local wall-clock shift times (never a timestamp - see CLAUDE.md
"Dates/times"), and every constraint declared inline in create_table()
rather than a separate ALTER TABLE (SQLite can't do most of those outside
Alembic's batch mode).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shift_types",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name_pl", sa.String(length=100), nullable=False),
        sa.Column("name_en", sa.String(length=100), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("color_hex", sa.String(length=7), nullable=False, server_default="#64748b"),
        sa.Column("active_weekdays", sa.Integer(), nullable=False),
        sa.Column("default_required_staff", sa.Integer(), nullable=False),
        sa.Column("default_min_staff", sa.Integer(), nullable=False),
        sa.Column("default_max_staff", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("code", name="uq_shift_types_code"),
        sa.CheckConstraint("end_time > start_time", name="ck_shift_types_time_order"),
        sa.CheckConstraint(
            "active_weekdays > 0 AND active_weekdays <= 127", name="ck_shift_types_active_weekdays"
        ),
        sa.CheckConstraint(
            "default_min_staff <= default_required_staff"
            " AND default_required_staff <= default_max_staff",
            name="ck_shift_types_staff_order",
        ),
    )

    op.create_table(
        "schedule_periods",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="DRAFT"),
        sa.Column("availability_opens_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("availability_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("year", "month", name="uq_schedule_periods_year_month"),
        sa.CheckConstraint("month BETWEEN 1 AND 12", name="ck_schedule_periods_month"),
        sa.CheckConstraint(
            "state IN ('DRAFT','COLLECTING','LOCKED','GENERATED','PUBLISHED')",
            name="ck_schedule_periods_state",
        ),
    )

    op.create_table(
        "shift_slots",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("period_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("shift_type_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("required_staff", sa.Integer(), nullable=False),
        sa.Column("min_staff", sa.Integer(), nullable=False),
        sa.Column("max_staff", sa.Integer(), nullable=False),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["period_id"], ["schedule_periods.id"]),
        sa.ForeignKeyConstraint(["shift_type_id"], ["shift_types.id"]),
        sa.UniqueConstraint(
            "period_id", "date", "shift_type_id", name="uq_shift_slots_period_date_type"
        ),
        sa.CheckConstraint(
            "min_staff <= required_staff AND required_staff <= max_staff",
            name="ck_shift_slots_staff_order",
        ),
    )
    op.create_index("ix_shift_slots_period_id", "shift_slots", ["period_id"])

    op.create_table(
        "availability_submissions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("period_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="NOT_STARTED"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reopened_by_manager", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["schedule_periods.id"]),
        sa.UniqueConstraint("user_id", "period_id", name="uq_availability_submissions_user_period"),
        sa.CheckConstraint(
            "status IN ('NOT_STARTED','DRAFT','SUBMITTED')",
            name="ck_availability_submissions_status",
        ),
    )
    op.create_index(
        "ix_availability_submissions_period_id", "availability_submissions", ["period_id"]
    )

    op.create_table(
        "availabilities",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("submission_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("shift_slot_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["submission_id"], ["availability_submissions.id"]),
        sa.ForeignKeyConstraint(["shift_slot_id"], ["shift_slots.id"]),
        sa.UniqueConstraint(
            "submission_id", "shift_slot_id", name="uq_availabilities_submission_slot"
        ),
        sa.CheckConstraint(
            "status IN ('UNAVAILABLE','AVAILABLE','PREFERRED')", name="ck_availabilities_status"
        ),
    )
    op.create_index("ix_availabilities_submission_id", "availabilities", ["submission_id"])

    op.create_table(
        "rules",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name_pl", sa.String(length=150), nullable=False),
        sa.Column("name_en", sa.String(length=150), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False, server_default="GLOBAL"),
        sa.Column("scope_ref", sa.String(length=100), nullable=True),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False, server_default="HARD"),
        sa.Column("weight", sa.Integer(), nullable=True),
        sa.Column("phase", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("code", name="uq_rules_code"),
        sa.CheckConstraint(
            "type IN ('MIN_AVAILABILITY_COUNT','MIN_AVAILABILITY_IN_SET',"
            "'MIN_AVAILABILITY_WEEKEND')",
            name="ck_rules_type",
        ),
        sa.CheckConstraint("scope IN ('GLOBAL','EMPLOYMENT_TYPE','USER')", name="ck_rules_scope"),
        sa.CheckConstraint("severity IN ('HARD','SOFT')", name="ck_rules_severity"),
        sa.CheckConstraint("phase IN ('AVAILABILITY','SCHEDULE','BOTH')", name="ck_rules_phase"),
    )


def downgrade() -> None:
    op.drop_table("rules")
    op.drop_table("availabilities")
    op.drop_table("availability_submissions")
    op.drop_table("shift_slots")
    op.drop_table("schedule_periods")
    op.drop_table("shift_types")
