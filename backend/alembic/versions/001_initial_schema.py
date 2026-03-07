"""Consolidated initial schema — all 15 tables + materialized view + indexes.

Revision ID: 001
Revises:
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("discord_webhook_url", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # --- sectors ---
    op.create_table(
        "sectors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    # --- stocks ---
    op.create_table(
        "stocks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker", sa.String(10), nullable=False, unique=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("sector_id", sa.Integer(), sa.ForeignKey("sectors.id"), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("market_cap", sa.BigInteger(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_stocks_ticker", "stocks", ["ticker"])
    op.create_index("ix_stocks_sector_id", "stocks", ["sector_id"])
    op.create_index("ix_stocks_industry", "stocks", ["industry"])
    op.execute("CREATE INDEX ix_stocks_is_active ON stocks (is_active) WHERE is_active = true")

    # --- articles ---
    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True, unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_processed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("key_phrases", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("event_category", sa.String(100), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.create_index("ix_articles_source", "articles", ["source"])
    op.create_index("ix_articles_is_processed", "articles", ["is_processed"])
    op.create_index("ix_articles_scraped_at", "articles", ["scraped_at"])

    # --- article_stocks ---
    op.create_table(
        "article_stocks",
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("stock_id", sa.Integer(), sa.ForeignKey("stocks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("confidence", sa.Numeric(5, 4), server_default=sa.text("1.0"), nullable=False),
    )

    # --- market_data_daily ---
    op.create_table(
        "market_data_daily",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stock_id", sa.Integer(), sa.ForeignKey("stocks.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(12, 4), nullable=True),
        sa.Column("high", sa.Numeric(12, 4), nullable=True),
        sa.Column("low", sa.Numeric(12, 4), nullable=True),
        sa.Column("close", sa.Numeric(12, 4), nullable=True),
        sa.Column("adj_close", sa.Numeric(12, 4), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.String(50), server_default=sa.text("'yfinance'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_market_data_daily_stock_id", "market_data_daily", ["stock_id"])
    op.create_unique_constraint("uq_market_data_daily_stock_date", "market_data_daily", ["stock_id", "date"])
    op.execute("CREATE INDEX ix_market_data_daily_stock_date_desc ON market_data_daily (stock_id, date DESC)")

    # --- market_data_intraday ---
    op.create_table(
        "market_data_intraday",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stock_id", sa.Integer(), sa.ForeignKey("stocks.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(12, 4), nullable=True),
        sa.Column("high", sa.Numeric(12, 4), nullable=True),
        sa.Column("low", sa.Numeric(12, 4), nullable=True),
        sa.Column("close", sa.Numeric(12, 4), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_market_data_intraday_stock_id", "market_data_intraday", ["stock_id"])
    op.create_unique_constraint(
        "uq_market_data_intraday_stock_timestamp", "market_data_intraday", ["stock_id", "timestamp"]
    )
    op.execute("CREATE INDEX ix_market_data_intraday_stock_ts_desc ON market_data_intraday (stock_id, timestamp DESC)")

    # --- sentiment_scores ---
    op.create_table(
        "sentiment_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stock_id", sa.Integer(), sa.ForeignKey("stocks.id"), nullable=True),
        sa.Column("label", sa.String(20), nullable=False),
        sa.Column("positive_score", sa.Numeric(6, 5), nullable=False),
        sa.Column("negative_score", sa.Numeric(6, 5), nullable=False),
        sa.Column("neutral_score", sa.Numeric(6, 5), nullable=False),
        sa.Column("model_version", sa.String(50), server_default=sa.text("'finbert-v1'"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_unique_constraint("uq_sentiment_scores_article_stock", "sentiment_scores", ["article_id", "stock_id"])
    op.create_index("ix_sentiment_scores_stock_processed", "sentiment_scores", ["stock_id", "processed_at"])

    # --- signals ---
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stock_id", sa.Integer(), sa.ForeignKey("stocks.id"), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("strength", sa.String(20), nullable=False),
        sa.Column("composite_score", sa.Numeric(8, 5), nullable=False),
        sa.Column("sentiment_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("price_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("volume_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("rsi_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("trend_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("article_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_signals_stock_id", "signals", ["stock_id"])
    op.create_index("ix_signals_generated_at", "signals", ["generated_at"])
    op.create_index("ix_signals_stock_generated", "signals", ["stock_id", "generated_at"])

    # --- signal_outcomes ---
    op.create_table(
        "signal_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("signal_id", sa.Integer(), sa.ForeignKey("signals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("signal_close", sa.Numeric(12, 4), nullable=False),
        sa.Column("outcome_close", sa.Numeric(12, 4), nullable=False),
        sa.Column("price_change_pct", sa.Numeric(8, 5), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("signal_id", "window_days"),
    )
    op.create_index("ix_signal_outcomes_signal_id", "signal_outcomes", ["signal_id"])
    op.create_index("ix_signal_outcomes_evaluated_at", "signal_outcomes", ["evaluated_at"])

    # --- signal_weights ---
    op.create_table(
        "signal_weights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sector_id", sa.Integer(), sa.ForeignKey("sectors.id"), nullable=True),
        sa.Column("sentiment_momentum", sa.Numeric(5, 4), nullable=False, server_default="0.3000"),
        sa.Column("sentiment_volume", sa.Numeric(5, 4), nullable=False, server_default="0.2000"),
        sa.Column("price_momentum", sa.Numeric(5, 4), nullable=False, server_default="0.1500"),
        sa.Column("volume_anomaly", sa.Numeric(5, 4), nullable=False, server_default="0.1000"),
        sa.Column("rsi", sa.Numeric(5, 4), nullable=False, server_default="0.1500"),
        sa.Column("trend", sa.Numeric(5, 4), nullable=False, server_default="0.1000"),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accuracy_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("sector_id"),
    )
    op.create_index("ix_signal_weights_sector_id", "signal_weights", ["sector_id"])

    # --- alert_configs ---
    op.create_table(
        "alert_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stock_id", sa.Integer(), sa.ForeignKey("stocks.id"), nullable=True),
        sa.Column("min_strength", sa.String(20), server_default=sa.text("'moderate'"), nullable=False),
        sa.Column("direction_filter", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("channel", sa.String(20), server_default=sa.text("'both'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # --- alert_logs ---
    op.create_table(
        "alert_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("signal_id", sa.Integer(), sa.ForeignKey("signals.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("success", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_alert_logs_user_sent", "alert_logs", ["user_id", "sent_at"])

    # --- watchlist_items ---
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stock_id", sa.Integer(), sa.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_unique_constraint("uq_watchlist_items_user_stock", "watchlist_items", ["user_id", "stock_id"])
    op.create_index("ix_watchlist_items_user_id", "watchlist_items", ["user_id"])

    # --- scrape_logs ---
    op.create_table(
        "scrape_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("articles_found", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("articles_new", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("errors", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_details", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_index("ix_scrape_logs_source", "scrape_logs", ["source"])

    # --- backtests ---
    op.create_table(
        "backtests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("stock_id", sa.Integer(), sa.ForeignKey("stocks.id"), nullable=True),
        sa.Column("sector_id", sa.Integer(), sa.ForeignKey("sectors.id"), nullable=True),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("start_date", sa.DateTime(timezone=False), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=False), nullable=False),
        sa.Column("starting_capital", sa.Numeric(12, 2), nullable=False, server_default="10000"),
        sa.Column("min_signal_strength", sa.String(20), nullable=False, server_default="moderate"),
        sa.Column("total_return_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("annualized_return_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("sharpe_ratio", sa.Numeric(8, 4), nullable=True),
        sa.Column("max_drawdown_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("win_rate_pct", sa.Numeric(6, 4), nullable=True),
        sa.Column("total_trades", sa.Integer(), nullable=True),
        sa.Column("avg_win_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("avg_loss_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("best_trade_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("worst_trade_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("final_equity", sa.Numeric(14, 2), nullable=True),
        sa.Column("equity_curve", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_backtests_user_status", "backtests", ["user_id", "status"])

    # --- backtest_trades ---
    op.create_table(
        "backtest_trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("backtest_id", sa.Integer(), sa.ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("trade_date", sa.DateTime(timezone=False), nullable=False),
        sa.Column("price", sa.Numeric(12, 4), nullable=False),
        sa.Column("shares", sa.Numeric(14, 6), nullable=False),
        sa.Column("position_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("portfolio_equity", sa.Numeric(14, 2), nullable=False),
        sa.Column("signal_score", sa.Numeric(8, 5), nullable=False),
        sa.Column("signal_direction", sa.String(20), nullable=False),
        sa.Column("signal_strength", sa.String(20), nullable=False),
        sa.Column("return_pct", sa.Numeric(8, 4), nullable=True),
    )
    op.create_index("ix_backtest_trades_backtest_id", "backtest_trades", ["backtest_id"])

    # --- materialized view: daily sentiment summary ---
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
    op.execute("CREATE UNIQUE INDEX ix_mv_daily_sentiment_stock_date ON mv_daily_sentiment_summary (stock_id, summary_date)")
    op.execute("CREATE INDEX ix_mv_daily_sentiment_date ON mv_daily_sentiment_summary (summary_date)")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_daily_sentiment_summary")
    op.drop_index("ix_backtest_trades_backtest_id", table_name="backtest_trades")
    op.drop_table("backtest_trades")
    op.drop_index("ix_backtests_user_status", table_name="backtests")
    op.drop_table("backtests")
    op.drop_table("scrape_logs")
    op.drop_table("watchlist_items")
    op.drop_table("alert_logs")
    op.drop_table("alert_configs")
    op.drop_index("ix_signal_weights_sector_id", table_name="signal_weights")
    op.drop_table("signal_weights")
    op.drop_index("ix_signal_outcomes_evaluated_at", table_name="signal_outcomes")
    op.drop_index("ix_signal_outcomes_signal_id", table_name="signal_outcomes")
    op.drop_table("signal_outcomes")
    op.drop_table("signals")
    op.drop_table("sentiment_scores")
    op.drop_table("market_data_intraday")
    op.drop_table("market_data_daily")
    op.drop_table("article_stocks")
    op.drop_table("articles")
    op.drop_table("stocks")
    op.drop_table("sectors")
    op.drop_table("users")
