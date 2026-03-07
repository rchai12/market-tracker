"""Add signal_outcomes and signal_weights tables for feedback loop.

Revision ID: 005
Revises: 004
Create Date: 2026-03-07
"""

import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
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

    op.create_table(
        "signal_weights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sector_id", sa.Integer(), sa.ForeignKey("sectors.id"), nullable=True),
        sa.Column("sentiment_momentum", sa.Numeric(5, 4), nullable=False, server_default="0.4000"),
        sa.Column("sentiment_volume", sa.Numeric(5, 4), nullable=False, server_default="0.2500"),
        sa.Column("price_momentum", sa.Numeric(5, 4), nullable=False, server_default="0.2000"),
        sa.Column("volume_anomaly", sa.Numeric(5, 4), nullable=False, server_default="0.1500"),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accuracy_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("sector_id"),
    )
    op.create_index("ix_signal_weights_sector_id", "signal_weights", ["sector_id"])


def downgrade() -> None:
    op.drop_index("ix_signal_weights_sector_id", table_name="signal_weights")
    op.drop_table("signal_weights")
    op.drop_index("ix_signal_outcomes_evaluated_at", table_name="signal_outcomes")
    op.drop_index("ix_signal_outcomes_signal_id", table_name="signal_outcomes")
    op.drop_table("signal_outcomes")
