"""benchmark_unique_index

Revision ID: 006
Revises: 005
Create Date: 2026-04-23

Adds UNIQUE INDEX on (portfolio_name, snapshot_date) in shadow_portfolio_snapshots.
Uses IF NOT EXISTS / IF EXISTS guards — safe for re-runs (idempotent).
"""
from typing import Sequence, Union

from alembic import op


revision: str = "006"
down_revision: Union[str, Sequence[str], None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_shadow_portfolio_unique "
        "ON shadow_portfolio_snapshots (portfolio_name, snapshot_date)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_shadow_portfolio_unique")
