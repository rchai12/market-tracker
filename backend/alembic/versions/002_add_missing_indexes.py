"""Add missing indexes for query performance.

Revision ID: 002
Revises: 001
Create Date: 2026-03-04
"""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # sentiment_scores(stock_id, processed_at) — signal_generator hits this 6+ times,
    # plus sentiment API timeline, trending, and sector summary endpoints
    op.create_index(
        "ix_sentiment_scores_stock_processed",
        "sentiment_scores",
        ["stock_id", "processed_at"],
    )

    # articles(scraped_at) — articles list ORDER BY scraped_at DESC
    op.create_index("ix_articles_scraped_at", "articles", ["scraped_at"])

    # market_data_daily(stock_id, date DESC) — range queries + ORDER BY date DESC
    op.execute(
        "CREATE INDEX ix_market_data_daily_stock_date_desc "
        "ON market_data_daily (stock_id, date DESC)"
    )

    # market_data_intraday(stock_id, timestamp DESC) — range queries + ORDER BY
    op.execute(
        "CREATE INDEX ix_market_data_intraday_stock_ts_desc "
        "ON market_data_intraday (stock_id, timestamp DESC)"
    )

    # signals(generated_at) — latest signals feed ORDER BY
    op.create_index("ix_signals_generated_at", "signals", ["generated_at"])

    # signals(stock_id, generated_at) — per-ticker signal history
    op.create_index(
        "ix_signals_stock_generated",
        "signals",
        ["stock_id", "generated_at"],
    )

    # stocks(is_active) — partial index for active stock filtering in worker tasks
    op.execute(
        "CREATE INDEX ix_stocks_is_active ON stocks (is_active) WHERE is_active = true"
    )

    # alert_logs(user_id, sent_at) — user's alert history listing
    op.create_index("ix_alert_logs_user_sent", "alert_logs", ["user_id", "sent_at"])

    # watchlist_items(user_id) — user's watchlist listing
    op.create_index("ix_watchlist_items_user_id", "watchlist_items", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_watchlist_items_user_id", "watchlist_items")
    op.drop_index("ix_alert_logs_user_sent", "alert_logs")
    op.drop_index("ix_stocks_is_active", "stocks")
    op.drop_index("ix_signals_stock_generated", "signals")
    op.drop_index("ix_signals_generated_at", "signals")
    op.execute("DROP INDEX IF EXISTS ix_market_data_intraday_stock_ts_desc")
    op.execute("DROP INDEX IF EXISTS ix_market_data_daily_stock_date_desc")
    op.drop_index("ix_articles_scraped_at", "articles")
    op.drop_index("ix_sentiment_scores_stock_processed", "sentiment_scores")
