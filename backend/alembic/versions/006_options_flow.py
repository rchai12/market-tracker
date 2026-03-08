"""Options flow: options_activity + cboe_put_call_ratio tables, options_score on signals, options weight.

Revision ID: 006
Revises: 005
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create options_activity table
    op.create_table(
        "options_activity",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("stock_id", sa.Integer, sa.ForeignKey("stocks.id"), nullable=False, index=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("total_call_volume", sa.BigInteger, nullable=True),
        sa.Column("total_put_volume", sa.BigInteger, nullable=True),
        sa.Column("total_call_oi", sa.BigInteger, nullable=True),
        sa.Column("total_put_oi", sa.BigInteger, nullable=True),
        sa.Column("put_call_ratio", sa.Numeric(6, 4), nullable=True),
        sa.Column("weighted_avg_iv", sa.Numeric(6, 4), nullable=True),
        sa.Column("atm_call_iv", sa.Numeric(6, 4), nullable=True),
        sa.Column("atm_put_iv", sa.Numeric(6, 4), nullable=True),
        sa.Column("iv_skew", sa.Numeric(8, 4), nullable=True),
        sa.Column("expirations_fetched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("data_quality", sa.String(20), nullable=False, server_default="full"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("stock_id", "date"),
    )

    # Create cboe_put_call_ratio table
    op.create_table(
        "cboe_put_call_ratio",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("date", sa.Date, unique=True, nullable=False),
        sa.Column("total_pc", sa.Numeric(6, 4), nullable=True),
        sa.Column("equity_pc", sa.Numeric(6, 4), nullable=True),
        sa.Column("index_pc", sa.Numeric(6, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Add options_score to signals
    op.add_column("signals", sa.Column("options_score", sa.Numeric(6, 5), nullable=True))

    # Add options weight to signal_weights
    op.add_column(
        "signal_weights",
        sa.Column("options", sa.Numeric(5, 4), nullable=False, server_default="0.08"),
    )


def downgrade() -> None:
    op.drop_column("signal_weights", "options")
    op.drop_column("signals", "options_score")
    op.drop_table("cboe_put_call_ratio")
    op.drop_table("options_activity")
