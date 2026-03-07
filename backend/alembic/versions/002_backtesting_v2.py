"""Backtesting v2: transaction costs, position sizing, stop-loss, benchmark.

Revision ID: 002
Revises: 001
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # backtests: v2 config fields
    op.add_column("backtests", sa.Column("commission_pct", sa.Numeric(6, 4), nullable=True))
    op.add_column("backtests", sa.Column("slippage_pct", sa.Numeric(6, 4), nullable=True))
    op.add_column("backtests", sa.Column("position_size_pct", sa.Numeric(5, 2), nullable=True))
    op.add_column("backtests", sa.Column("stop_loss_pct", sa.Numeric(5, 2), nullable=True))
    op.add_column("backtests", sa.Column("take_profit_pct", sa.Numeric(5, 2), nullable=True))

    # backtests: benchmark comparison
    op.add_column("backtests", sa.Column("benchmark_ticker", sa.String(10), nullable=True))
    op.add_column("backtests", sa.Column("benchmark_total_return_pct", sa.Numeric(10, 4), nullable=True))
    op.add_column("backtests", sa.Column("benchmark_annualized_return_pct", sa.Numeric(10, 4), nullable=True))
    op.add_column("backtests", sa.Column("alpha", sa.Numeric(10, 4), nullable=True))
    op.add_column("backtests", sa.Column("beta", sa.Numeric(8, 4), nullable=True))
    op.add_column("backtests", sa.Column("benchmark_equity_curve", sa.Text(), nullable=True))

    # backtest_trades: exit reason
    op.add_column("backtest_trades", sa.Column("exit_reason", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("backtest_trades", "exit_reason")

    op.drop_column("backtests", "benchmark_equity_curve")
    op.drop_column("backtests", "beta")
    op.drop_column("backtests", "alpha")
    op.drop_column("backtests", "benchmark_annualized_return_pct")
    op.drop_column("backtests", "benchmark_total_return_pct")
    op.drop_column("backtests", "benchmark_ticker")

    op.drop_column("backtests", "take_profit_pct")
    op.drop_column("backtests", "stop_loss_pct")
    op.drop_column("backtests", "position_size_pct")
    op.drop_column("backtests", "slippage_pct")
    op.drop_column("backtests", "commission_pct")
