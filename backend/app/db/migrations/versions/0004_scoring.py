"""score criteria, employee scores

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-12

Adds ScoreCriterion and EmployeeScore (ARCHITECTURE.md ss3.4). `weight` is
sa.Numeric (exact Decimal on every dialect, unlike Float) so the "active
weights sum to exactly 1.0" rule in app/services/score_service.py holds
without floating-point drift. Every constraint is declared inline in
create_table(), per CLAUDE.md "Database portability".
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "score_criteria",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name_pl", sa.String(length=150), nullable=False),
        sa.Column("name_en", sa.String(length=150), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("weight", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("scale_min", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("scale_max", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("code", name="uq_score_criteria_code"),
        sa.CheckConstraint("scale_min < scale_max", name="ck_score_criteria_scale_order"),
        sa.CheckConstraint("weight >= 0", name="ck_score_criteria_weight_non_negative"),
    )

    op.create_table(
        "employee_scores",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("criterion_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("set_by_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["criterion_id"], ["score_criteria.id"]),
        sa.ForeignKeyConstraint(["set_by_user_id"], ["users.id"]),
        sa.CheckConstraint("value BETWEEN 1 AND 5", name="ck_employee_scores_value_range"),
    )
    op.create_index(
        "ix_employee_scores_user_criterion",
        "employee_scores",
        ["user_id", "criterion_id", "effective_from"],
    )


def downgrade() -> None:
    op.drop_table("employee_scores")
    op.drop_table("score_criteria")
