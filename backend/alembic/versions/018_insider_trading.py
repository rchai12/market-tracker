"""Insider Form 4 transactions: table + signals.insider_score + weight columns.

Revision ID: 018
Revises: 017
"""

import sqlalchemy as sa

from alembic import op

revision = "018"
down_revision = "017"


def upgrade() -> None:
    op.create_table(
        "insider_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stock_id", sa.Integer(), sa.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("insider_name", sa.String(200), nullable=True),
        sa.Column("insider_title", sa.String(200), nullable=True),
        sa.Column("transaction_type", sa.String(10), nullable=False),
        sa.Column("shares", sa.Numeric(15, 2), nullable=True),
        sa.Column("price_per_share", sa.Numeric(10, 4), nullable=True),
        sa.Column("transaction_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "stock_id",
            "insider_name",
            "transaction_date",
            "transaction_type",
            "shares",
            name="uq_insider_tx_dedup",
        ),
    )
    op.create_index("idx_insider_stock_date", "insider_transactions", ["stock_id", "transaction_date"])
    op.add_column("signals", sa.Column("insider_score", sa.Float(), nullable=True))
    op.add_column(
        "signal_weights",
        sa.Column("insider", sa.Numeric(5, 4), nullable=False, server_default="0.08"),
    )
    op.add_column(
        "regime_adaptive_weights",
        sa.Column("insider", sa.Numeric(5, 4), nullable=False, server_default="0.08"),
    )


def downgrade() -> None:
    op.drop_column("regime_adaptive_weights", "insider")
    op.drop_column("signal_weights", "insider")
    op.drop_column("signals", "insider_score")
    op.drop_index("idx_insider_stock_date", table_name="insider_transactions")
    op.drop_table("insider_transactions")
