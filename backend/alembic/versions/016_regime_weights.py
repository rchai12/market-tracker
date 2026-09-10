"""Regime-conditional weights + analyst column on signal_weights.

Revision ID: 016
Revises: 015
"""

import sqlalchemy as sa

from alembic import op

revision = "016"
down_revision = "015"


def upgrade() -> None:
    op.add_column(
        "signal_weights",
        sa.Column("analyst", sa.Numeric(5, 4), nullable=False, server_default="0.07"),
    )
    op.create_table(
        "regime_adaptive_weights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sector_id", sa.Integer(), sa.ForeignKey("sectors.id"), nullable=True, index=True),
        sa.Column("regime", sa.String(20), nullable=False),
        sa.Column("sentiment_momentum", sa.Numeric(5, 4), nullable=False),
        sa.Column("sentiment_volume", sa.Numeric(5, 4), nullable=False),
        sa.Column("price_momentum", sa.Numeric(5, 4), nullable=False),
        sa.Column("volume_anomaly", sa.Numeric(5, 4), nullable=False),
        sa.Column("earnings", sa.Numeric(5, 4), nullable=False, server_default="0.10"),
        sa.Column("options", sa.Numeric(5, 4), nullable=False, server_default="0.08"),
        sa.Column("analyst", sa.Numeric(5, 4), nullable=False, server_default="0.07"),
        sa.Column("rsi", sa.Numeric(5, 4), nullable=False, server_default="0.0"),
        sa.Column("trend", sa.Numeric(5, 4), nullable=False, server_default="0.0"),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("accuracy_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "sector_id",
            "regime",
            name="uq_regime_adaptive_weights_sector_regime",
            postgresql_nulls_not_distinct=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("regime_adaptive_weights")
    op.drop_column("signal_weights", "analyst")
