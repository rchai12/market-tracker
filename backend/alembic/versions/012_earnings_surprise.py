"""Earnings surprise: earnings_estimates table, signals.earnings_score, signal_weights.earnings.

Revision ID: 012
Revises: 011
"""

import sqlalchemy as sa
from alembic import op

revision = "012"
down_revision = "011"


def upgrade() -> None:
    op.create_table(
        "earnings_estimates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "stock_id",
            sa.Integer(),
            sa.ForeignKey("stocks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("earnings_date", sa.Date(), nullable=False, index=True),
        sa.Column("fiscal_quarter", sa.String(10), nullable=True),
        sa.Column("estimated_eps", sa.Float(), nullable=True),
        sa.Column("actual_eps", sa.Float(), nullable=True),
        sa.Column("surprise_pct", sa.Float(), nullable=True),  # stored as percentage: 15.2 = 15.2% beat
        sa.Column("estimated_revenue", sa.Float(), nullable=True),
        sa.Column("actual_revenue", sa.Float(), nullable=True),
        sa.Column("revenue_surprise_pct", sa.Float(), nullable=True),
        sa.Column("guidance_change", sa.String(20), nullable=True),  # populated by Phase 21d (LLM)
        sa.Column("reported", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("stock_id", "earnings_date", name="uq_earnings_stock_date"),
    )

    op.add_column("signals", sa.Column("earnings_score", sa.Float(), nullable=True))
    op.add_column(
        "signal_weights",
        sa.Column("earnings", sa.Numeric(5, 4), nullable=False, server_default="0.1"),
    )


def downgrade() -> None:
    op.drop_column("signal_weights", "earnings")
    op.drop_column("signals", "earnings_score")
    op.drop_table("earnings_estimates")
