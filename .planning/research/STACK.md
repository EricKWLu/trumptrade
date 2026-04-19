# Stack: TrumpTrade

**Project:** TrumpTrade automated political signal trading bot
**Researched:** 2026-04-19
**Confidence note:** WebSearch, Bash, and WebFetch tools were unavailable during this research session. All recommendations are drawn from training data (cutoff August 2025). Versions should be verified against PyPI before pinning in requirements.txt. Confidence levels reflect this constraint.

---

## Backend

### Core Framework: FastAPI 0.111+

**Package:** `fastapi`, `uvicorn[standard]`
**Confidence:** HIGH (stable, dominant choice for Python async APIs as of mid-2025)

FastAPI is the correct choice here, not Flask or Django. Reasons:

- Native async/await support means the polling loops, LLM calls, and Alpaca API calls can all be non-blocking in the same process
- Automatic OpenAPI docs at `/docs` — useful for debugging the trading API during development
- Pydantic v2 models built in — you get validated trade signal objects, settings schemas, and API responses without extra code
- WebSocket support built in — needed for pushing live feed updates to the dashboard
- Uvicorn as the ASGI server handles concurrent connections without threading complexity

**Why not Flask:** Synchronous by default; async support is bolted on and fragile. Would require threads or separate processes for background polling.
**Why not Django:** Far too heavy; ORM and admin overhead are not needed for a single-user tool.

```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
pydantic>=2.7.0
```

---

## Social Media Ingestion

### X/Twitter: Tweepy 4.x

**Package:** `tweepy`
**Confidence:** HIGH (Tweepy is the canonical Python X/Twitter client)

Tweepy wraps the X API v2 endpoints. For this project, the relevant access pattern is:

- **Basic tier** (~$100/month): Provides read access to public tweets. Use `tweepy.Client` (v2 interface) with `get_users_tweets()` polling on Trump's user ID (`@realDonaldTrump`).
- Poll interval: 60–120 seconds is safe under Basic tier rate limits (500k tweets/month read cap).
- Store the last-seen tweet ID to avoid reprocessing on each poll.

```python
client = tweepy.Client(bearer_token=BEARER_TOKEN)
response = client.get_users_tweets(user_id=TRUMP_USER_ID, since_id=last_seen_id)
```

**Why not Twitter streaming (filtered stream):** Streaming requires a higher tier than Basic as of 2024. Polling is explicitly listed as sufficient in PROJECT.md.
**Why not snscrape:** Unmaintained as of 2023 after Twitter/X locked down unauthenticated scraping. Do not use.

```
tweepy>=4.14.0
```

### Truth Social: Custom HTTP Scraper (no library available)

**Package:** `httpx`, `beautifulsoup4`
**Confidence:** MEDIUM — Truth Social has no official API and no maintained Python library. The approach below is based on how Truth Social exposes its public feed.

Truth Social is built on a Mastodon fork. Its public profile endpoint follows the Mastodon API pattern:

```
GET https://truthsocial.com/api/v1/accounts/:account_id/statuses
```

This is a JSON REST endpoint, not HTML — no BeautifulSoup parsing needed unless the endpoint breaks. Use `httpx` (async-native) to poll it. Trump's account ID on Truth Social is stable (`107780257626128497` as of research date, but verify).

```python
import httpx

async def fetch_truth_social_posts(since_id: str | None = None):
    url = "https://truthsocial.com/api/v1/accounts/107780257626128497/statuses"
    params = {"limit": 20}
    if since_id:
        params["since_id"] = since_id
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        return resp.json()
```

**WARNING — HIGH FRAGILITY:** This endpoint is undocumented and unofficial. Truth Social can block it, change the structure, or require authentication at any time. This is the single highest-risk component in the stack. Build with a circuit breaker so a broken scraper doesn't halt trading.

**Why not Playwright/Selenium for Truth Social:** The Mastodon-compatible JSON endpoint is far more reliable and parseable than HTML scraping. Use the JSON endpoint until it breaks, then fall back to HTML scraping.

```
httpx>=0.27.0
beautifulsoup4>=4.12.0   # fallback HTML parsing if JSON endpoint breaks
lxml>=5.2.0              # fast HTML parser backend for BS4
```

---

## LLM / Analysis

### Primary: OpenAI Python SDK (GPT-4o) or Anthropic SDK (Claude)

**Packages:** `openai`, `anthropic`
**Confidence:** HIGH for both SDKs being current and maintained

**Recommendation: Start with `openai` + GPT-4o-mini for cost control.**

Rationale:
- GPT-4o-mini is significantly cheaper than GPT-4o (~$0.15/1M input tokens vs $5) and more than capable of classifying a 280-character tweet as BULLISH / BEARISH / NEUTRAL with a confidence score.
- `openai>=1.30.0` uses the modern `openai.OpenAI()` client (not the legacy module-level calls).
- Structured output via `response_format={"type": "json_object"}` gives you clean machine-readable signals.
- Claude (via `anthropic` SDK) is an equally valid alternative — Claude Sonnet 3.5 is strong at structured classification tasks and has comparable pricing. The choice comes down to which API key you already have.

**Signal schema (Pydantic):**

```python
class TradeSignal(BaseModel):
    signal: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    confidence: float  # 0.0 - 1.0
    affected_sectors: list[str]
    affected_tickers: list[str]
    reasoning: str
```

**Keyword rule layer:** Implement as a pure Python function that runs BEFORE the LLM call. If keywords match (e.g., "tariff", "sanction", "drill", "ban"), override or augment the LLM signal. This prevents LLM API calls for obvious cases and provides a fallback when the LLM API is down.

```
openai>=1.30.0
# OR
anthropic>=0.28.0
```

---

## Trading

### Alpaca: alpaca-py (NOT alpaca-trade-api)

**Package:** `alpaca-py`
**Confidence:** HIGH — `alpaca-trade-api` is the legacy SDK; `alpaca-py` is Alpaca's current official SDK as of 2023+

`alpaca-trade-api` (the old library) is in maintenance mode. `alpaca-py` is the replacement with full support for v2 REST and WebSocket data streams.

Key usage patterns for this project:

```python
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# Paper trading — swap base_url for live
client = TradingClient(api_key=API_KEY, secret_key=SECRET_KEY, paper=True)

# Submit market order with attached stop-loss
order = client.submit_order(
    MarketOrderRequest(
        symbol="AAPL",
        qty=10,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
        stop_loss=StopLossRequest(stop_price=145.00)
    )
)
```

**Paper vs live:** Set `paper=True` to route to `paper-api.alpaca.markets`. Switch to `paper=False` for live trading. Keep this as a config toggle, never hardcoded.

**Historical data for comparison mode:** Use `alpaca.data.historical.StockHistoricalDataClient` to pull OHLCV bars for SPY, QQQ, and the user's watchlist tickers.

```
alpaca-py>=0.20.0
```

---

## Scheduling / Background Tasks

### APScheduler 3.x (NOT Celery)

**Package:** `apscheduler`
**Confidence:** HIGH

**Why APScheduler, not Celery:**
- Celery requires a Redis or RabbitMQ broker. That's a separate process, a Docker container, or a cloud service — significant operational overhead for a single-user tool.
- APScheduler runs in-process within the FastAPI application. No broker, no worker process, no message queue.
- For this project, "scheduling" means: poll Truth Social every 90s, poll X/Twitter every 60s, run daily P&L reconciliation at market close. APScheduler handles all of this trivially.

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
scheduler.add_job(poll_truth_social, "interval", seconds=90)
scheduler.add_job(poll_twitter, "interval", seconds=60)
scheduler.add_job(daily_reconcile, "cron", hour=16, minute=5)  # after NYSE close
scheduler.start()
```

Use `AsyncIOScheduler` (not `BackgroundScheduler`) since the FastAPI app runs on asyncio.

**Why not Celery:** Overkill. Adds Redis dependency, worker process management, and distributed task complexity for what is essentially a polling loop.
**Why not cron + subprocess:** Loses shared state with the FastAPI process; harder to coordinate "is trading paused?" flags.

```
apscheduler>=3.10.0
```

---

## Frontend / Dashboard

### React + Vite (TypeScript) with shadcn/ui components

**Packages:** React 18, Vite 5, TanStack Query (React Query) v5, shadcn/ui
**Confidence:** MEDIUM-HIGH — React + Vite is the dominant 2025 SPA stack; shadcn/ui has become the standard component library since 2023

**Frontend serves as a read-heavy monitoring dashboard.** The primary interactions are:
- Live feed of incoming posts with signal annotations
- Portfolio value chart (comparison mode: TrumpTrade vs SPY vs QQQ vs random)
- Trade log table with filters
- Settings form (watchlist tickers, risk parameters, pause/resume toggle)

**Communication pattern:**
- Polling (TanStack Query with `refetchInterval`) for trade log and portfolio state — simple and sufficient
- WebSocket for the live post feed — FastAPI has native WebSocket support, push new posts as they arrive

**Why React + Vite over Next.js:** No SSR needed for a single-user local dashboard. Vite gives faster dev iteration than Next.js for a pure SPA.
**Why shadcn/ui over MUI or Chakra:** shadcn/ui is copy-paste components (no runtime library dependency), Tailwind-based, and has excellent chart primitives via Recharts integration. The trade log table and portfolio chart are first-class use cases.
**Why TanStack Query over SWR:** More mature, better devtools, built-in background refetch with interval.

**Charts:** Recharts (already part of shadcn/ui chart components) for portfolio comparison lines. No need for a separate charting library.

**Alternative if React is too heavy:** Use HTMX + Jinja2 templates served directly from FastAPI. This works well for the settings form and trade log table but is awkward for the real-time live feed. Only choose this if you want zero JavaScript build tooling.

---

## Database

### SQLite via SQLAlchemy 2.x (async) + Alembic

**Packages:** `sqlalchemy[asyncio]`, `aiosqlite`, `alembic`
**Confidence:** HIGH for single-user local deployment

**Why SQLite:**
- Single-user personal tool. No concurrent write contention.
- Zero operational overhead — no database server process, no Docker container, just a file.
- SQLAlchemy 2.x with `aiosqlite` driver provides full async support compatible with FastAPI.
- The data volume is tiny: a few hundred trades per year, a few thousand posts.

**Why SQLAlchemy over raw SQL / sqlite3 module:**
- Alembic migrations let you evolve the schema without dropping tables.
- ORM models serve as the canonical schema definition — no schema drift between Python and DB.
- Easy to swap to PostgreSQL later if needed (just change the connection string).

**Schema sketch:**

```python
class Post(Base):
    __tablename__ = "posts"
    id: Mapped[str] = mapped_column(primary_key=True)  # platform post ID
    platform: Mapped[str]       # "truth_social" | "twitter"
    content: Mapped[str]
    posted_at: Mapped[datetime]
    signal: Mapped[str | None]  # BULLISH / BEARISH / NEUTRAL
    confidence: Mapped[float | None]
    processed_at: Mapped[datetime | None]

class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[str] = mapped_column(primary_key=True)  # Alpaca order ID
    ticker: Mapped[str]
    side: Mapped[str]           # BUY / SELL
    qty: Mapped[float]
    fill_price: Mapped[float | None]
    post_id: Mapped[str]        # FK to posts.id
    executed_at: Mapped[datetime]
    stop_loss_price: Mapped[float | None]
    mode: Mapped[str]           # "paper" | "live"
```

**Why not PostgreSQL from the start:** Operational complexity not justified for a single-user tool. PostgreSQL becomes the right call if this ever becomes multi-user or deployed to a server.
**Why not MongoDB:** No document model benefits here; structured relational data (trades reference posts) maps naturally to SQL.

```
sqlalchemy[asyncio]>=2.0.30
aiosqlite>=0.20.0
alembic>=1.13.0
```

---

## Configuration & Environment

### python-dotenv + Pydantic Settings

**Package:** `python-dotenv`, `pydantic-settings`
**Confidence:** HIGH

Use `pydantic-settings` (`BaseSettings`) to load all secrets and config from environment variables / `.env` file with automatic type coercion and validation at startup.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_paper_mode: bool = True
    openai_api_key: str
    twitter_bearer_token: str
    poll_interval_twitter_seconds: int = 60
    poll_interval_truth_seconds: int = 90
    max_daily_loss_pct: float = 0.05
    default_position_size_pct: float = 0.02

    class Config:
        env_file = ".env"
```

```
pydantic-settings>=2.2.0
python-dotenv>=1.0.0
```

---

## What NOT to Use

| Technology | Why Not | Use Instead |
|---|---|---|
| `alpaca-trade-api` | Legacy SDK, maintenance mode since 2023 | `alpaca-py` |
| `snscrape` | Unmaintained; X/Twitter blocked unauthenticated scraping in 2023 | `tweepy` with paid API key |
| Celery + Redis | Massive operational overhead for a single-user polling loop | `apscheduler` |
| Selenium / Playwright for Truth Social | Fragile, slow, resource-heavy; JSON endpoint is available | `httpx` against Mastodon-compat endpoint |
| Flask | Synchronous; async bolt-on is awkward for concurrent polling + trading | `fastapi` |
| Django | Monolithic framework overhead not justified; ORM/admin not needed | `fastapi` + `sqlalchemy` |
| PostgreSQL (initially) | Operational overhead for single-user; overkill for this data volume | SQLite via `aiosqlite` |
| Next.js | SSR not needed; adds build complexity for a local SPA | React + Vite |
| MUI / Chakra | Heavier runtime bundles; shadcn/ui is now the standard | `shadcn/ui` + Tailwind |
| pandas for signal processing | Unnecessary for per-tweet classification; adds weight | Plain Python dicts + Pydantic models |
| `requests` library | Synchronous; blocks event loop in async FastAPI context | `httpx` (async-native) |

---

## Full Dependency Summary

```
# requirements.txt

# Backend
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
pydantic>=2.7.0
pydantic-settings>=2.2.0
python-dotenv>=1.0.0

# Social Media
tweepy>=4.14.0
httpx>=0.27.0
beautifulsoup4>=4.12.0
lxml>=5.2.0

# LLM
openai>=1.30.0
# anthropic>=0.28.0  # alternative

# Trading
alpaca-py>=0.20.0

# Scheduling
apscheduler>=3.10.0

# Database
sqlalchemy[asyncio]>=2.0.30
aiosqlite>=0.20.0
alembic>=1.13.0
```

---

## Confidence Assessment

| Area | Confidence | Notes |
|---|---|---|
| FastAPI + Uvicorn | HIGH | Dominant Python async web stack; stable since 2022 |
| alpaca-py | HIGH | Official current Alpaca SDK; alpaca-trade-api is explicitly deprecated |
| Tweepy | HIGH | Canonical X/Twitter Python client; well-documented |
| Truth Social scraping (httpx + Mastodon endpoint) | MEDIUM | Mastodon-compat endpoint confirmed stable as of 2024; fragility is inherent to unofficial access |
| OpenAI SDK | HIGH | Stable v1.x client since late 2023 |
| APScheduler | HIGH | Mature library; in-process scheduling is correct for this scope |
| SQLite + SQLAlchemy 2.x async | HIGH | SQLAlchemy 2.0 async support is production-stable |
| React + Vite + shadcn/ui | MEDIUM-HIGH | Dominant 2024-2025 stack; shadcn/ui meteoric adoption is training-data confirmed |

**Versions caveat:** All version pins are based on training data (cutoff August 2025). Before starting development, run `pip index versions <package>` or check PyPI for the latest stable release of each dependency.
