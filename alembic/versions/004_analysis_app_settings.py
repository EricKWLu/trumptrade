"""analysis_app_settings

Revision ID: 004
Revises: 6e3709bc5279
Create Date: 2026-04-21

Seeds llm_provider, llm_model, confidence_threshold defaults into app_settings.
Uses INSERT OR IGNORE so existing values are never overwritten.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "004"
down_revision: Union[str, Sequence[str], None] = "6e3709bc5279"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('llm_provider', 'anthropic')")
    op.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('llm_model', 'claude-haiku-4-5-20251001')")
    op.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('confidence_threshold', '0.7')")


def downgrade() -> None:
    op.execute(
        "DELETE FROM app_settings WHERE key IN ('llm_provider', 'llm_model', 'confidence_threshold')"
    )
