"""Paper portfolio: portfolios, positions, trades, daily snapshots.

Revision ID: 015
Revises: 014
"""

import sqlalchemy as sa

from alembic import op

revision = "015"
down_revision = "014"


def upgrade() -> None:
    op.create_table(
        "paper_portfolios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("inception_date", sa.Date(), nullable=False),
        sa.Column("starting_capital", sa.Float(), nullable=False),
        sa.Column("current_cash", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("benchmark_ticker", sa.String(10), nullable=False, server_default="SPY"),
        sa.Column("benchmark_inception_price", sa.Float(), nullable=True),
    )

    op.create_table(
        "paper_positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "portfolio_id",
            sa.Integer(),
            sa.ForeignKey("paper_portfolios.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("stock_id", sa.Integer(), sa.ForeignKey("stocks.id"), nullable=False, index=True),
        sa.Column("entry_signal_id", sa.Integer(), sa.ForeignKey("signals.id"), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("shares", sa.Float(), nullable=False),
        sa.Column("stop_loss_price", sa.Float(), nullable=True),
        sa.Column("take_profit_price", sa.Float(), nullable=True),
        sa.UniqueConstraint("portfolio_id", "stock_id", name="uq_paper_position_stock"),
    )

    op.create_table(
        "paper_trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "portfolio_id",
            sa.Integer(),
            sa.ForeignKey("paper_portfolios.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("stock_id", sa.Integer(), sa.ForeignKey("stocks.id"), nullable=False, index=True),
        sa.Column("entry_signal_id", sa.Integer(), sa.ForeignKey("signals.id"), nullable=True),
        sa.Column("exit_signal_id", sa.Integer(), sa.ForeignKey("signals.id"), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("exit_price", sa.Float(), nullable=False),
        sa.Column("shares", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("return_pct", sa.Float(), nullable=False),
        sa.Column("exit_reason", sa.String(30), nullable=False),
    )

    op.create_table(
        "paper_portfolio_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "portfolio_id",
            sa.Integer(),
            sa.ForeignKey("paper_portfolios.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("total_value", sa.Float(), nullable=False),
        sa.Column("cash", sa.Float(), nullable=False),
        sa.Column("equity_value", sa.Float(), nullable=False),
        sa.Column("open_positions", sa.Integer(), nullable=False),
        sa.Column("benchmark_price", sa.Float(), nullable=True),
        sa.Column("daily_return_pct", sa.Float(), nullable=True),
        sa.Column("cumulative_return_pct", sa.Float(), nullable=True),
        sa.Column("benchmark_cumulative_return_pct", sa.Float(), nullable=True),
        sa.UniqueConstraint("portfolio_id", "snapshot_date", name="uq_paper_snapshot_date"),
    )


def downgrade() -> None:
    op.drop_table("paper_portfolio_snapshots")
    op.drop_table("paper_trades")
    op.drop_table("paper_positions")
    op.drop_table("paper_portfolios")
