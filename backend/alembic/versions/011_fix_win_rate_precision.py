"""Fix win_rate_pct column precision: NUMERIC(6,4) overflows at 100.0.

Revision ID: 011
Revises: 010
"""

import sqlalchemy as sa
from alembic import op

revision = "011"
down_revision = "010"


def upgrade() -> None:
    op.alter_column(
        "backtests",
        "win_rate_pct",
        type_=sa.Numeric(7, 4),
        existing_type=sa.Numeric(6, 4),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "backtests",
        "win_rate_pct",
        type_=sa.Numeric(6, 4),
        existing_type=sa.Numeric(7, 4),
        existing_nullable=True,
    )
