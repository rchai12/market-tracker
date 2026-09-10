"""Analyst score: gated 8th signal component from LLM-extracted ratings.

Revision ID: 014
Revises: 013
"""

import sqlalchemy as sa

from alembic import op

revision = "014"
down_revision = "013"


def upgrade() -> None:
    op.add_column("signals", sa.Column("analyst_score", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("signals", "analyst_score")
