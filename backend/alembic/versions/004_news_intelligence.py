"""News intelligence: add duplicate_group_id column and event_category index.

Revision ID: 004
Revises: 003
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("duplicate_group_id", sa.Integer, nullable=True))
    op.create_index("ix_articles_duplicate_group_id", "articles", ["duplicate_group_id"])
    op.create_index("ix_articles_event_category", "articles", ["event_category"])


def downgrade() -> None:
    op.drop_index("ix_articles_event_category", table_name="articles")
    op.drop_index("ix_articles_duplicate_group_id", table_name="articles")
    op.drop_column("articles", "duplicate_group_id")
