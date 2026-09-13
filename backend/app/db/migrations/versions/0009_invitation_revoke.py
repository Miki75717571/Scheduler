"""invitation revoke support

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-13

Adds `invitations.revoked_at` (CLAUDE.md JOB 8: "resend and revoke" on the
invitations screen). A plain nullable column, added with `add_column` per
0006's precedent for a no-new-constraint addition.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("invitations", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("invitations", "revoked_at")
