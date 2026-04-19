"""Entry point for `python -m trumptrade` and the `trumptrade` CLI script."""
from __future__ import annotations


def main() -> None:
    """Start the TrumpTrade server. Wired to uvicorn in Plan 05."""
    # Placeholder — FastAPI app creation added in Plan 05 (01-PLAN-05)
    import uvicorn
    from trumptrade.core.app import create_app

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
