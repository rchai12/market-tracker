"""ML ensemble: add ml_score/ml_direction/ml_confidence to signals, create ml_models table.

Revision ID: 005
Revises: 004
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add ML columns to signals table
    op.add_column("signals", sa.Column("ml_score", sa.Numeric(8, 5), nullable=True))
    op.add_column("signals", sa.Column("ml_direction", sa.String(20), nullable=True))
    op.add_column("signals", sa.Column("ml_confidence", sa.Numeric(5, 4), nullable=True))
    op.create_index("ix_signals_ml_score", "signals", ["ml_score"])

    # Create ml_models table
    op.create_table(
        "ml_models",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("sector_id", sa.Integer, sa.ForeignKey("sectors.id"), nullable=True, index=True),
        sa.Column("model_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("feature_count", sa.Integer, nullable=False, server_default="6"),
        sa.Column("training_samples", sa.Integer, nullable=False, server_default="0"),
        sa.Column("validation_accuracy", sa.Numeric(5, 2), nullable=True),
        sa.Column("validation_f1", sa.Numeric(5, 4), nullable=True),
        sa.Column("model_path", sa.String(500), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("trained_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("feature_importances", sa.Text, nullable=True),
        sa.Column("training_config", sa.Text, nullable=True),
        sa.UniqueConstraint("sector_id"),
    )


def downgrade() -> None:
    op.drop_table("ml_models")
    op.drop_index("ix_signals_ml_score", table_name="signals")
    op.drop_column("signals", "ml_confidence")
    op.drop_column("signals", "ml_direction")
    op.drop_column("signals", "ml_score")
