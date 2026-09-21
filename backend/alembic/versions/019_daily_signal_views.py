"""Daily signal views: tables + signals.trading_date.

Revision ID: 019
Revises: 018
"""

import sqlalchemy as sa

from alembic import op

revision = "019"
down_revision = "018"


def upgrade() -> None:
    op.create_table(
        "daily_signal_views",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "stock_id",
            sa.Integer(),
            sa.ForeignKey("stocks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("trading_date", sa.Date(), nullable=False),
        sa.Column("net_score", sa.Float(), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("conviction", sa.Float(), nullable=False),
        sa.Column("signal_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("baseline_close", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("stock_id", "trading_date", name="uq_daily_signal_views_stock_date"),
    )
    op.create_index("idx_daily_view_stock_date", "daily_signal_views", ["stock_id", "trading_date"])
    op.create_index("idx_daily_view_date", "daily_signal_views", ["trading_date"])

    op.create_table(
        "daily_signal_view_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "daily_view_id",
            sa.Integer(),
            sa.ForeignKey("daily_signal_views.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("outcome_close", sa.Float(), nullable=False),
        sa.Column("price_change_pct", sa.Float(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("daily_view_id", "window_days", name="uq_daily_view_outcome_window"),
    )

    op.add_column("signals", sa.Column("trading_date", sa.Date(), nullable=True))
    op.create_index("idx_signal_trading_date", "signals", ["stock_id", "trading_date"])
    op.execute(
        """
        UPDATE signals
        SET trading_date = (generated_at AT TIME ZONE 'America/New_York')::date
        WHERE trading_date IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("idx_signal_trading_date", table_name="signals")
    op.drop_column("signals", "trading_date")
    op.drop_table("daily_signal_view_outcomes")
    op.drop_index("idx_daily_view_date", table_name="daily_signal_views")
    op.drop_index("idx_daily_view_stock_date", table_name="daily_signal_views")
    op.drop_table("daily_signal_views")
