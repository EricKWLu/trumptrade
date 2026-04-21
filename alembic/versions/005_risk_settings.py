"""risk_settings

Revision ID: 005
Revises: 004
Create Date: 2026-04-21

Seeds max_position_size_pct, max_daily_loss_dollars, signal_staleness_minutes into app_settings.
Uses INSERT OR IGNORE so existing values are never overwritten (idempotent).

Note: stop_loss_pct already exists from initial schema (6e3709bc5279) — NOT re-inserted here.
Note: position_size_pct and max_daily_loss_pct (old keys from initial schema) are preserved
      untouched; Phase 5 uses new keys with different names and semantics.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "005"
down_revision: Union[str, Sequence[str], None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # D-09: default max_position_size_pct = 2.0 (conservative for personal paper bot)
    op.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('max_position_size_pct', '2.0')")
    # D-13: default max_daily_loss_dollars = 500.0
    op.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('max_daily_loss_dollars', '500.0')")
    # D-15: default signal_staleness_minutes = 5
    op.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('signal_staleness_minutes', '5')")


def downgrade() -> None:
    op.execute(
        "DELETE FROM app_settings WHERE key IN "
        "('max_position_size_pct', 'max_daily_loss_dollars', 'signal_staleness_minutes')"
    )
