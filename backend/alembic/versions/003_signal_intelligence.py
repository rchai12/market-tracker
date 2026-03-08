"""Signal intelligence: add sentiment_volume_score column.

Revision ID: 003
Revises: 002
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signals", sa.Column("sentiment_volume_score", sa.Numeric(8, 4), nullable=True))


def downgrade() -> None:
    op.drop_column("signals", "sentiment_volume_score")
