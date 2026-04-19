# TrumpTrade — Project Guide

## What This Is

Automated trading bot that monitors Trump's Truth Social + X/Twitter posts, analyzes them with AI + keyword rules, and executes trades on a user-defined watchlist via Alpaca API. Single-user personal tool with a web dashboard.

## Stack

- **Backend**: Python, FastAPI, APScheduler (in-process polling)
- **Trading**: `alpaca-py` (NOT `alpaca-trade-api` — that's deprecated)
- **Social ingestion**: `httpx` (Truth Social Mastodon endpoint), `tweepy` (X/Twitter)
- **LLM**: OpenAI or Anthropic SDK for signal classification
- **DB**: SQLite + SQLAlchemy 2.x async + Alembic
- **Frontend**: React 18 + Vite + shadcn/ui + TanStack Query v5

## GSD Workflow

This project uses GSD for structured phase-based development.

### Key commands
- `/gsd-discuss-phase N` — gather context before planning a phase
- `/gsd-plan-phase N` — create PLAN.md for a phase
- `/gsd-execute-phase N` — execute the plan
- `/gsd-progress` — check current state

### Current state
See `.planning/STATE.md` for current phase and progress.
See `.planning/ROADMAP.md` for all phases and requirements.

## Critical Rules

1. **Never use `alpaca-trade-api`** — use `alpaca-py` (`from alpaca.trading.client import TradingClient`)
2. **Never use `requests`** — use `httpx` (async-native; `requests` blocks the asyncio event loop)
3. **Paper mode is default** — `TRADING_MODE=paper` unless explicitly set to `live`
4. **Bracket orders only** — stop-loss must be atomic with entry order, never a separate submission
5. **Risk checks inside the queue** — all position sizing and daily loss cap checks happen inside the executor after dequeue, never before
6. **Dashboard reads Alpaca live API** — never trust bot's internal state for money-related display
7. **LLM never suggests new tickers** — it classifies against watchlist only; structured output must be Pydantic-validated

## Architecture

```
[Truth Social poller] ─┐
                       ├─► [SHA-256 dedup] ─► [LLM analyzer + keyword rules]
[X/Twitter poller]  ───┘         │                        │
                                 │                        ▼
                           [audit store]        [confidence gate 0.7]
                                                          │
                                                          ▼
                                                [asyncio.Queue risk guard]
                                                (position size, daily cap, market hours)
                                                          │
                                              ┌───────────┴───────────┐
                                              ▼                       ▼
                                    [Alpaca executor]        [shadow portfolios]
                                   (paper or live)           (SPY/QQQ/random NAV)
                                              │
                                              ▼
                                    [SQLite audit log]
                                              │
                                              ▼
                                    [FastAPI + WebSocket]
                                              │
                                              ▼
                                    [React dashboard]
```

## Secrets

Never commit: `.env`, API keys, Alpaca credentials, OpenAI/Anthropic keys
