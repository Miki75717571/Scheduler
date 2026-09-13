"""schedule run pre-run snapshot and revert tracking

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-12

Adds `schedule_runs.pre_run_snapshot` (every assignment that existed for the
period at the moment a run was created, so the manager can revert to it with
one click) plus `reverted_at`/`reverted_by_user_id` to record that a revert
happened (app/models/schedule_run.py, app/services/solver_service.py's
`revert_run`). Plain `add_column` calls, no new constraints - CLAUDE.md's
"declare constraints inline inside create_table()" only bites when a
constraint needs adding after the fact, which none of these do.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("schedule_runs", sa.Column("pre_run_snapshot", sa.JSON(), nullable=True))
    op.add_column(
        "schedule_runs", sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "schedule_runs", sa.Column("reverted_by_user_id", sa.Uuid(as_uuid=True), nullable=True)
    )
    with op.batch_alter_table("schedule_runs") as batch_op:
        batch_op.create_foreign_key(
            "fk_schedule_runs_reverted_by_user_id", "users", ["reverted_by_user_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("schedule_runs") as batch_op:
        batch_op.drop_constraint("fk_schedule_runs_reverted_by_user_id", type_="foreignkey")
        batch_op.drop_column("reverted_by_user_id")
        batch_op.drop_column("reverted_at")
        batch_op.drop_column("pre_run_snapshot")
