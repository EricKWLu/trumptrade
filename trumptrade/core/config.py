"""Application configuration — secrets loaded from .env, runtime settings in DB."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Secrets — loaded from .env only (D-08)
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    x_api_key: str = ""
    x_api_secret: str = ""
    x_bearer_token: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    groq_api_key: str = ""  # Optional — required only when llm_provider = "groq" (D-03)
    truth_social_account_id: str = "107780257626128497"  # realDonaldTrump's Mastodon account ID
    truth_social_account_username: str = "realDonaldTrump"  # informational
    truth_social_token: str = ""       # Optional — unused by httpx poller (kept for backwards compat)
    truth_social_username: str = ""    # Optional — unused by httpx poller
    truth_social_password: str = ""    # Optional — unused by httpx poller

    # Non-secret app config
    debug: bool = False
    db_url: str = "sqlite+aiosqlite:///./trumptrade.db"

    # NOTE: position_size_pct, stop_loss_pct, trading_mode, etc. live in the
    # app_settings DB table (D-09), NOT here. They are runtime-editable.


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings singleton.

    Reads .env exactly once. In tests, call get_settings.cache_clear() then
    monkeypatch env vars to override.
    """
    return Settings()
