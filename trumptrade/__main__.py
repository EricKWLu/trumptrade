"""Entry point for `python -m trumptrade` and the `trumptrade` CLI script.

Starts FastAPI via uvicorn with APScheduler running in-process.
Both mechanisms dispatch here:
  - python -m trumptrade  -> Python executes this __main__.py
  - trumptrade            -> pyproject.toml [project.scripts] calls main()
"""
from __future__ import annotations

import logging


def main() -> None:
    """Start the TrumpTrade server.

    Initializes structured logging, then hands control to uvicorn which
    creates the asyncio event loop. APScheduler starts inside the FastAPI
    lifespan context once the loop is running.
    """
    import uvicorn

    from trumptrade.core.app import create_app
    from trumptrade.core.config import get_settings
    from trumptrade.core.logging import setup_logging

    settings = get_settings()

    # Initialize structured JSON logging before any output
    log_level = "DEBUG" if settings.debug else "INFO"
    setup_logging(level=log_level)

    logger = logging.getLogger(__name__)
    logger.info("TrumpTrade entry point — starting uvicorn")

    # Pass the app object directly (NOT a string like "trumptrade.core.app:app").
    # Using a string path with create_app() causes uvicorn to import a different
    # module instance than the one holding the scheduler, breaking startup.
    app = create_app()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level=log_level.lower(),
    )


if __name__ == "__main__":
    main()
