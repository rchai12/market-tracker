"""Add industry column to stocks table for sub-sector granularity.

Revision ID: 004
Revises: 003
Create Date: 2026-03-06
"""

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stocks", sa.Column("industry", sa.String(100), nullable=True))
    op.create_index("ix_stocks_industry", "stocks", ["industry"])


def downgrade() -> None:
    op.drop_index("ix_stocks_industry", table_name="stocks")
    op.drop_column("stocks", "industry")
