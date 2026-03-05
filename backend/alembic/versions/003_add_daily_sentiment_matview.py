"""Add materialized view for daily sentiment aggregates per stock.

Pre-computes daily sentiment counts and averages to avoid expensive
3-table JOINs + GROUP BY on millions of rows for sector/trending endpoints.

Revision ID: 003
Revises: 002
Create Date: 2026-03-04
"""

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE MATERIALIZED VIEW mv_daily_sentiment_summary AS
        SELECT
            ss.stock_id,
            DATE(ss.processed_at AT TIME ZONE 'UTC') AS summary_date,
            COUNT(*) AS article_count,
            SUM(CASE WHEN ss.label = 'positive' THEN 1 ELSE 0 END) AS positive_count,
            SUM(CASE WHEN ss.label = 'negative' THEN 1 ELSE 0 END) AS negative_count,
            SUM(CASE WHEN ss.label = 'neutral' THEN 1 ELSE 0 END) AS neutral_count,
            AVG(ss.positive_score) AS avg_positive,
            AVG(ss.negative_score) AS avg_negative,
            AVG(ss.neutral_score) AS avg_neutral
        FROM sentiment_scores ss
        WHERE ss.stock_id IS NOT NULL
        GROUP BY ss.stock_id, DATE(ss.processed_at AT TIME ZONE 'UTC')
    """)

    op.execute("""
        CREATE UNIQUE INDEX ix_mv_daily_sentiment_stock_date
        ON mv_daily_sentiment_summary (stock_id, summary_date)
    """)

    op.execute("""
        CREATE INDEX ix_mv_daily_sentiment_date
        ON mv_daily_sentiment_summary (summary_date)
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_daily_sentiment_summary")
