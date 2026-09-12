"""assignments, audit log, schedule-phase rule types

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-12

Adds Assignment and AuditLog (ARCHITECTURE.md ss3.6), and widens rules.type's
CHECK constraint for the Phase 3 schedule-phase rule types. The constraint
change goes through `op.batch_alter_table` (recreate="auto", the default) so
it becomes a real ALTER on Postgres and a table-rebuild only where the
backend actually requires one (SQLite can't drop/add a CHECK constraint any
other way) - same portability approach as everywhere else, see CLAUDE.md
"Database portability".
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_OLD_RULE_TYPES = "'MIN_AVAILABILITY_COUNT','MIN_AVAILABILITY_IN_SET','MIN_AVAILABILITY_WEEKEND'"
_NEW_RULE_TYPES = (
    "'MIN_AVAILABILITY_COUNT','MIN_AVAILABILITY_IN_SET','MIN_AVAILABILITY_WEEKEND',"
    "'ONE_SHIFT_PER_DAY','MIN_REST_HOURS','MAX_CONSECUTIVE_DAYS','MIN_SHIFTS_PER_MONTH',"
    "'MAX_SHIFTS_PER_MONTH','MAX_WEEKEND_SHIFTS'"
)


def upgrade() -> None:
    op.create_table(
        "assignments",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("shift_slot_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=10), nullable=False, server_default="MANUAL"),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "modified_after_publish", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("created_by_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["shift_slot_id"], ["shift_slots.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("shift_slot_id", "user_id", name="uq_assignments_slot_user"),
        sa.CheckConstraint("source IN ('AUTO','MANUAL')", name="ck_assignments_source"),
    )
    op.create_index("ix_assignments_shift_slot_id", "assignments", ["shift_slot_id"])
    op.create_index("ix_assignments_user_id", "assignments", ["user_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("actor_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("period_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["schedule_periods.id"]),
    )
    op.create_index("ix_audit_logs_period_id_at", "audit_logs", ["period_id", "at"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])

    with op.batch_alter_table("rules") as batch_op:
        batch_op.drop_constraint("ck_rules_type", type_="check")
        batch_op.create_check_constraint("ck_rules_type", f"type IN ({_NEW_RULE_TYPES})")


def downgrade() -> None:
    with op.batch_alter_table("rules") as batch_op:
        batch_op.drop_constraint("ck_rules_type", type_="check")
        batch_op.create_check_constraint("ck_rules_type", f"type IN ({_OLD_RULE_TYPES})")

    op.drop_table("audit_logs")
    op.drop_table("assignments")
