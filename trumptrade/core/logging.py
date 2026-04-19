"""Logging configuration for TrumpTrade — structured JSON output."""
from __future__ import annotations

import logging
import sys
from typing import Any


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON for machine readability."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime, timezone

        log_entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger with JSON formatter to stdout.

    Call once at application startup (in __main__.py before uvicorn.run).
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)
