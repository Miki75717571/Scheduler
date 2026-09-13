"""rebalance solver weight defaults for a small crew

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-13

Updates the existing `solver_weight_configs` row(s) to the new defaults
tuned for a ~7-person crew with one-person shifts (CLAUDE.md JOB 6c) - see
app/scheduling/domain.py's SolverWeights docstring for the full rationale.
Only rows still exactly at the old defaults are touched, so an admin who has
already customized their weights keeps their own values.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TABLE = sa.table(
    "solver_weight_configs",
    sa.column("contract_min_shortfall", sa.Integer()),
    sa.column("fairness_spread", sa.Integer()),
    sa.column("unpopular_shift_spread", sa.Integer()),
    sa.column("score_weight", sa.Integer()),
)

_OLD = {
    "contract_min_shortfall": 1000,
    "fairness_spread": 30,
    "unpopular_shift_spread": 25,
    "score_weight": 10,
}
_NEW = {
    "contract_min_shortfall": 2500,
    "fairness_spread": 60,
    "unpopular_shift_spread": 50,
    "score_weight": 5,
}


def upgrade() -> None:
    op.execute(
        _TABLE.update()
        .where(
            _TABLE.c.contract_min_shortfall == _OLD["contract_min_shortfall"],
            _TABLE.c.fairness_spread == _OLD["fairness_spread"],
            _TABLE.c.unpopular_shift_spread == _OLD["unpopular_shift_spread"],
            _TABLE.c.score_weight == _OLD["score_weight"],
        )
        .values(**_NEW)
    )


def downgrade() -> None:
    op.execute(
        _TABLE.update()
        .where(
            _TABLE.c.contract_min_shortfall == _NEW["contract_min_shortfall"],
            _TABLE.c.fairness_spread == _NEW["fairness_spread"],
            _TABLE.c.unpopular_shift_spread == _NEW["unpopular_shift_spread"],
            _TABLE.c.score_weight == _NEW["score_weight"],
        )
        .values(**_OLD)
    )
