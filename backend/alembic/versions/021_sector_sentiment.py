"""Sector sentiment gated component on signals.

Revision ID: 021
Revises: 020
"""

import sqlalchemy as sa

from alembic import op

revision = "021"
down_revision = "020"


def upgrade() -> None:
    op.add_column("signals", sa.Column("sector_sentiment_score", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("signals", "sector_sentiment_score")
