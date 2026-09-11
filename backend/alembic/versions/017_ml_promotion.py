"""Persist whether ML was gated into the live composite.

Revision ID: 017
Revises: 016
"""

import sqlalchemy as sa

from alembic import op

revision = "017"
down_revision = "016"


def upgrade() -> None:
    op.add_column(
        "signals",
        sa.Column("has_ml", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("signals", "has_ml")
