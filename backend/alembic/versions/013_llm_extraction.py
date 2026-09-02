"""LLM extraction: articles.llm_extracted tracking column.

Revision ID: 013
Revises: 012
"""

import sqlalchemy as sa
from alembic import op

revision = "013"
down_revision = "012"


def upgrade() -> None:
    # Track which articles have been submitted to LLM extraction.
    # NULL = not yet attempted; True = extracted; False = attempted but failed/skipped.
    op.add_column(
        "articles",
        sa.Column("llm_extracted", sa.Boolean(), nullable=True, server_default=sa.text("NULL")),
    )
    op.create_index("ix_articles_llm_extracted", "articles", ["llm_extracted"])


def downgrade() -> None:
    op.drop_index("ix_articles_llm_extracted", table_name="articles")
    op.drop_column("articles", "llm_extracted")
