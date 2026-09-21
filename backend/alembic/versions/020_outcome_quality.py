"""Outcome quality: excess returns, raw signal counts.

Revision ID: 020
Revises: 019
"""

import sqlalchemy as sa

from alembic import op

revision = "020"
down_revision = "019"


def upgrade() -> None:
    op.add_column("daily_signal_view_outcomes", sa.Column("sector_return_pct", sa.Float(), nullable=True))
    op.add_column("daily_signal_view_outcomes", sa.Column("excess_return_pct", sa.Float(), nullable=True))
    op.add_column("daily_signal_views", sa.Column("raw_signal_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("daily_signal_views", "raw_signal_count")
    op.drop_column("daily_signal_view_outcomes", "excess_return_pct")
    op.drop_column("daily_signal_view_outcomes", "sector_return_pct")
