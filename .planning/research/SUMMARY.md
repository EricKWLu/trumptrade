# Research Summary: TrumpTrade

## Recommended Stack

| Library | Purpose | Why |
|---|---|---|
| `fastapi` + `uvicorn[standard]` | Async API server + WebSocket | Native async/await, concurrent polling without thread management |
| `alpaca-py>=0.20.0` | Brokerage execution | Current official Alpaca SDK — `alpaca-trade-api` is deprecated |
| `tweepy>=4.14.0` | X/Twitter ingestion | Canonical X API v2 client — `snscrape` dead since 2023 |
| `httpx>=0.27.0` | Truth Social ingestion | Async HTTP against Mastodon-compatible JSON endpoint |
| `openai>=1.30.0` | LLM signal classification | GPT-4o-mini for cost; Anthropic SDK equal alternative |
| `apscheduler>=3.10.0` | In-process polling scheduler | No Celery/Redis needed for single-user tool |
| `sqlalchemy[asyncio]>=2.0.30` + `aiosqlite` + `alembic` | Async SQLite ORM + migrations | Zero ops overhead; easy PostgreSQL upgrade path |
| `pydantic-settings>=2.2.0` | Type-validated config from `.env` | Validated at startup, not at first use |
| React 18 + Vite + shadcn/ui + TanStack Query v5 | Web dashboard | Dominant 2025 SPA stack; Recharts for comparison charts |

**Critical corrections:** Use `alpaca-py` not `alpaca-trade-api`. Use `httpx` not `requests` (blocks asyncio event loop).

## Table Stakes Features

- Truth Social polling with heartbeat monitoring (fragile — must have alerting built simultaneously)
- X/Twitter polling via Tweepy with rate-limit budget tracking
- SHA-256 content deduplication before any signal routing
- LLM sentiment classification with Pydantic-validated structured output
- Keyword rule layer as override/fallback on AI analysis
- Paper trading mode via Alpaca (must be default and tested first)
- User-defined watchlist (LLM never discovers tickers outside it)
- Position sizing as % of portfolio
- Bracket stop-loss orders (atomic — never two separate orders)
- Max daily loss cap (reads live Alpaca account, not local counter)
- Live post feed + trade log + portfolio view on dashboard
- Bot on/off kill switch

## Differentiators

- **Benchmark comparison (SPY/QQQ/random)** — answers "am I beating the market?" via shadow NAV portfolios
- **Confidence threshold gate** (default 0.7) — logs but never executes low-confidence signals
- **Full signal audit trail** — raw LLM prompt + response + keyword matches + final action stored per signal
- **Post relevance pre-filter** — skips short/repost/no-financial-keywords posts before LLM call
- **Duplicate-within-1hr suppression** — same theme = 1 trade, not 3

## Architecture Overview

TrumpTrade is a linear event-driven pipeline in a single Python process. Two platform pollers (Truth Social + X/Twitter) converge at a SHA-256 dedup store, flow through the LLM analyzer (with keyword override), into a single-threaded `asyncio.Queue` risk guard (position size, daily loss cap, market hours), then to the Alpaca executor. The mode flag (paper/live) is a single config enum consumed only at the executor — the entire pipeline upstream is identical in both modes. The shadow portfolio engine is a passive observer of the post-risk-guard signal stream, doing pure NAV math without placing orders. The dashboard is read-only, reading from SQLite and Alpaca live API.

## Build Order

1. **Project setup** — `.env`, Pydantic Settings, SQLAlchemy schema, Alembic migrations, security gitignore
2. **Alpaca executor** — Paper trades with bracket stop-loss, `TradingMode` enum, kill-switch endpoint (stub signals)
3. **Ingestion pipeline** — X/Twitter + Truth Social pollers, SHA-256 dedup store, heartbeat alert
4. **LLM analysis + signal generation** — Structured output, keyword rules, confidence gate, post pre-filter, audit trail
5. **Risk guard + pipeline integration** — asyncio.Queue chokepoint, position sizing, daily loss cap, market hours guard
6. **Web dashboard** — React + Vite, live feed (WebSocket), trade log, portfolio view, settings
7. **Benchmark comparison** — SPY/QQQ/random shadow portfolios, comparison charts
8. **Live trading unlock** — Two-step confirmation UI, account sanity check, mode indicator

## Top 5 Pitfalls to Avoid

1. **Truth Social silent failure** — zero posts returned looks identical to "no new posts"; build heartbeat alert (0 posts in 6hr daytime window = alert) alongside the scraper
2. **LLM hallucination / prompt injection** — enforce Pydantic schema validation; discard if validation fails; confidence floor 0.7; LLM never suggests tickers outside watchlist
3. **Race condition bypassing risk checks** — single `asyncio.Queue` chokepoint; risk checks inside executor after dequeue, not before enqueue; daily loss cap reads live Alpaca
4. **Paper-to-live fill assumptions** — use bracket orders from day one; compute stop-loss from actual fill price (not submitted price); handle partial fills
5. **X/Twitter rate limit exhaustion** — calculate polling budget before writing code; implement rate-limit-aware retry; alert at 80% monthly usage

## Key Corrections to PROJECT.md

1. Use `alpaca-py` not `alpaca-trade-api` (deprecated)
2. Truth Social uses undocumented Mastodon-compatible JSON API — not HTML scraping — but still the highest-fragility component
3. No Celery — APScheduler inside FastAPI process is correct for single-user scope
4. Stop-losses must use bracket orders (atomic), not separate submissions
5. Paper/live must be a single config enum, not two code branches
6. Dashboard position data must read from Alpaca live API, not bot's internal state
7. Market hours check is mandatory — Trump posts at all hours; stale signals must be discarded
