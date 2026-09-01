"""Signal formula refactor: market_regime on signals. RSI/trend become regime-only.

Revision ID: 010
Revises: 008
"""

import sqlalchemy as sa
from alembic import op

revision = "010"
down_revision = "008"


def upgrade() -> None:
    op.add_column("signals", sa.Column("market_regime", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("signals", "market_regime")
