"""Add rsi_score and trend_score to signals, rsi and trend to signal_weights.

Revision ID: 006
Revises: 005
Create Date: 2026-03-07
"""

import sqlalchemy as sa
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new score columns to signals table
    op.add_column("signals", sa.Column("rsi_score", sa.Numeric(6, 5), nullable=True))
    op.add_column("signals", sa.Column("trend_score", sa.Numeric(6, 5), nullable=True))

    # Add new weight columns to signal_weights table
    op.add_column(
        "signal_weights",
        sa.Column("rsi", sa.Numeric(5, 4), nullable=False, server_default="0.1500"),
    )
    op.add_column(
        "signal_weights",
        sa.Column("trend", sa.Numeric(5, 4), nullable=False, server_default="0.1000"),
    )

    # Update server defaults on existing weight columns to reflect new 6-component split
    op.alter_column("signal_weights", "sentiment_momentum", server_default="0.3000")
    op.alter_column("signal_weights", "sentiment_volume", server_default="0.2000")
    op.alter_column("signal_weights", "price_momentum", server_default="0.1500")
    op.alter_column("signal_weights", "volume_anomaly", server_default="0.1000")


def downgrade() -> None:
    # Restore original server defaults
    op.alter_column("signal_weights", "sentiment_momentum", server_default="0.4000")
    op.alter_column("signal_weights", "sentiment_volume", server_default="0.2500")
    op.alter_column("signal_weights", "price_momentum", server_default="0.2000")
    op.alter_column("signal_weights", "volume_anomaly", server_default="0.1500")

    op.drop_column("signal_weights", "trend")
    op.drop_column("signal_weights", "rsi")
    op.drop_column("signals", "trend_score")
    op.drop_column("signals", "rsi_score")
