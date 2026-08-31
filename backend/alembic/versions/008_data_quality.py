"""Data quality gates: article quality_score, canonical_article_id, retail_sentiment_score.

Revision ID: 008
Revises: 007
"""

import sqlalchemy as sa
from alembic import op

revision = "008"
down_revision = "007"


def upgrade() -> None:
    op.add_column("articles", sa.Column("quality_score", sa.Float(), nullable=True))
    op.create_index("ix_articles_quality_score", "articles", ["quality_score"])

    op.add_column("articles", sa.Column("canonical_article_id", sa.Integer(), nullable=True))
    op.create_index("ix_articles_canonical_article_id", "articles", ["canonical_article_id"])
    op.create_foreign_key(
        "fk_articles_canonical_article_id",
        "articles",
        "articles",
        ["canonical_article_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("signals", sa.Column("retail_sentiment_score", sa.Numeric(6, 5), nullable=True))


def downgrade() -> None:
    op.drop_column("signals", "retail_sentiment_score")
    op.drop_constraint("fk_articles_canonical_article_id", "articles", type_="foreignkey")
    op.drop_index("ix_articles_canonical_article_id", table_name="articles")
    op.drop_column("articles", "canonical_article_id")
    op.drop_index("ix_articles_quality_score", table_name="articles")
    op.drop_column("articles", "quality_score")
