"""schedule runs, solver weight config, employee preference debt

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-12

Adds ScheduleRun and SolverWeightConfig (ARCHITECTURE.md ss3.6, ss4.1) for
Phase 5's CP-SAT solver, plus `users.preference_debt`
(ARCHITECTURE.md ss4.2). `solver_weight_configs` is seeded with one default
row here so `SolverWeightConfigRepository.get_or_create_default` always has
something to read even before an admin ever tunes it - every constraint is
declared inline in create_table(), per CLAUDE.md "Database portability".
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_DEFAULT_WEIGHTS_TABLE = sa.table(
    "solver_weight_configs",
    sa.column("id", sa.Uuid(as_uuid=True)),
    sa.column("understaffing", sa.Integer()),
    sa.column("contract_min_shortfall", sa.Integer()),
    sa.column("denied_preference", sa.Integer()),
    sa.column("fairness_spread", sa.Integer()),
    sa.column("unpopular_shift_spread", sa.Integer()),
    sa.column("score_weight", sa.Integer()),
    sa.column("preference_debt", sa.Integer()),
)


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("preference_debt", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "schedule_runs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("period_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="PENDING"),
        sa.Column("algorithm_version", sa.String(length=40), nullable=False),
        sa.Column("params_snapshot", sa.JSON(), nullable=False),
        sa.Column("objective_value", sa.Float(), nullable=True),
        sa.Column("solve_time_ms", sa.Integer(), nullable=True),
        sa.Column("solver_status", sa.String(length=30), nullable=True),
        sa.Column("stats", sa.JSON(), nullable=True),
        sa.Column("diagnostics", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["period_id"], ["schedule_periods.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCESS','FAILED')", name="ck_schedule_runs_status"
        ),
    )
    op.create_index("ix_schedule_runs_period_id", "schedule_runs", ["period_id"])

    op.create_table(
        "solver_weight_configs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("understaffing", sa.Integer(), nullable=False, server_default="10000"),
        sa.Column("contract_min_shortfall", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("denied_preference", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("fairness_spread", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("unpopular_shift_spread", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("score_weight", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("preference_debt", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
    )
    op.bulk_insert(
        _DEFAULT_WEIGHTS_TABLE,
        [
            {
                "id": uuid.uuid4(),
                "understaffing": 10000,
                "contract_min_shortfall": 1000,
                "denied_preference": 20,
                "fairness_spread": 30,
                "unpopular_shift_spread": 25,
                "score_weight": 10,
                "preference_debt": 15,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("solver_weight_configs")
    op.drop_index("ix_schedule_runs_period_id", table_name="schedule_runs")
    op.drop_table("schedule_runs")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("preference_debt")
