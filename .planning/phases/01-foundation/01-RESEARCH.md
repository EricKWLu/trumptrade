# Research: Phase 1 — Foundation

**Researched:** 2026-04-19
**Domain:** Python package scaffolding, SQLAlchemy 2.x async, Alembic migrations, FastAPI lifespan, Pydantic Settings v2, React/Vite/shadcn/ui
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Domain sub-packages: `trumptrade/ingestion/`, `trumptrade/analysis/`, `trumptrade/trading/`, `trumptrade/risk/`, `trumptrade/dashboard/` — one module per future phase domain
- **D-02:** Shared utilities in `trumptrade/core/` — holds config loading, DB session factory, logging setup, and the FastAPI app factory
- **D-03:** All domain sub-packages stubbed out in Phase 1 with empty `__init__.py` files — consistent import paths from day one, no renaming later
- **D-04:** Entry point: `python -m trumptrade` starts both FastAPI (via uvicorn) and APScheduler in a single process
- **D-05:** Full schema defined in Phase 1 — all tables created in a single Alembic migration: `watchlist`, `app_settings`, `posts`, `signals`, `orders`, `fills`, `shadow_portfolio_snapshots`, `keyword_rules`
- **D-06:** `shadow_portfolio_snapshots` table: columns `id`, `portfolio_name` (SPY/QQQ/random), `snapshot_date`, `nav_value`, `cash`, `positions_json`
- **D-07:** Separate `orders` and `fills` tables — matches Alpaca's model, handles partial fills correctly
- **D-08:** `.env` holds secrets only: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `X_API_KEY`, `X_API_SECRET`, `X_BEARER_TOKEN`, `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY`), `TRUTH_SOCIAL_ACCOUNT_ID`
- **D-09:** Everything runtime-editable lives in the `app_settings` DB table
- **D-10:** Alembic migration seeds safe defaults: `position_size_pct=2.0`, `stop_loss_pct=5.0`, `max_daily_loss_pct=10.0`, `confidence_threshold=0.7`, `trading_mode=paper`, `bot_enabled=false`
- **D-11:** `frontend/` directory at project root alongside `trumptrade/` Python package
- **D-12:** Frontend scaffold: Vite + React 18 + shadcn/ui + TanStack Query v5

### Claude's Discretion

- Exact logging format and level (structured JSON logging preferred)
- `pyproject.toml` with `[project.scripts]` for the entry point
- Specific SQLAlchemy model field types and constraints beyond what's implied by the schema

### Deferred Ideas (OUT OF SCOPE)

- Docker / docker-compose setup
- APScheduler job definitions (Phase 3 defines actual polling jobs; Phase 1 only wires up the scheduler instance)
- FastAPI route definitions beyond health check
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SETT-01 | User can add and remove stock tickers from the watchlist; bot only ever trades tickers on the watchlist | Watchlist table in DB schema; app_settings seeding pattern; FastAPI skeleton to receive future watchlist CRUD routes |
</phase_requirements>

---

## Summary

Phase 1 is pure scaffolding — no business logic, just the floor that everything else builds on. The primary technical challenges are: (1) getting pyproject.toml right so `python -m trumptrade` works after `pip install -e .`; (2) using SQLAlchemy 2.x declarative syntax correctly with async session factory; (3) wiring Alembic for an async engine, which requires a sync runner bridge; and (4) initializing shadcn/ui against a Vite project, which changed significantly with Tailwind v4.

The single most common mistake in this stack is Alembic's env.py: developers configure a sync engine and wonder why it ignores async models, or configure an async engine but forget the `run_sync()` bridge. The official Alembic async template (available via `alembic init --template async`) resolves this and should be used verbatim. The second most common mistake is `expire_on_commit=True` on the async session factory, which triggers implicit lazy loads after commit — always set `expire_on_commit=False` with async sessions.

**Primary recommendation:** Use `alembic init --template async` to generate the correct env.py skeleton, wire `target_metadata = Base.metadata` in env.py, place all 8 table models in `trumptrade/core/models.py` before running `alembic revision --autogenerate`, then seed `app_settings` defaults in the same migration's `upgrade()` function.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Package entry point | Python runtime (`__main__.py`) | pyproject.toml scripts | `python -m trumptrade` dispatches to `__main__.py`; scripts entry point creates a CLI alias |
| DB session factory | API / Backend (`trumptrade/core/db.py`) | — | Single async engine + session factory imported by all phases |
| Config loading | API / Backend (`trumptrade/core/config.py`) | — | Pydantic Settings reads .env; DB settings table read at runtime by settings service |
| FastAPI app factory | API / Backend (`trumptrade/core/app.py`) | — | Creates and configures the FastAPI instance, registers routers |
| APScheduler wiring | API / Backend (`__main__.py` lifespan) | — | Scheduler starts/stops in FastAPI lifespan, no separate process |
| DB schema + migrations | Database / Storage (Alembic) | SQLAlchemy models | Alembic owns schema evolution; models are the source of truth |
| Frontend scaffold | Browser / Client (`frontend/`) | — | Separate Vite app, communicates with FastAPI over HTTP |

---

## Python Project Setup (pyproject.toml)

### How `python -m trumptrade` Works

Python's `-m` flag looks for `trumptrade/__main__.py` and executes it as `__main__`. This works regardless of pyproject.toml — it only requires the package to be importable (i.e., installed or on `PYTHONPATH`). The `[project.scripts]` entry point creates a CLI alias (e.g., `trumptrade` → calls a function), which is separate from and in addition to the `-m` mechanism.

For this project both mechanisms can coexist: `python -m trumptrade` runs `__main__.py`, and after `pip install -e .` the `trumptrade` CLI command (if defined) calls the same function.

### Exact pyproject.toml Structure

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "trumptrade"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.29.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.2.0",
    "sqlalchemy[asyncio]>=2.0.30",
    "aiosqlite>=0.20.0",
    "alembic>=1.13.0",
    "apscheduler>=3.10.0",
    "httpx>=0.27.0",
    "tweepy>=4.14.0",
    "openai>=1.30.0",
    "alpaca-py>=0.20.0",
    "beautifulsoup4>=4.12.0",
    "lxml>=5.2.0",
]

[project.scripts]
trumptrade = "trumptrade.__main__:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["trumptrade*"]
```

**Critical:** After creating pyproject.toml, run `pip install -e .` from the project root. This makes `trumptrade` importable as a package and registers the CLI entry point. Without this, `python -m trumptrade` will fail with `No module named trumptrade`.

**Why setuptools over hatchling:** Either works. Setuptools is more familiar, requires no extra install, and `[tool.setuptools.packages.find]` is explicit. Hatchling is simpler but adds a dependency. Use setuptools for this project.

[VERIFIED: PyPI - setuptools is pre-installed with pip; WebSearch pypa.io docs]

### Package Directory Structure

```
trump_trade/                      ← project root (repo root)
├── pyproject.toml
├── .env                          ← secrets only, gitignored
├── .env.example                  ← template, committed to git
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 0001_initial_schema.py
├── trumptrade/                   ← Python package
│   ├── __init__.py
│   ├── __main__.py               ← entry point
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py             ← Pydantic Settings
│   │   ├── db.py                 ← engine + session factory
│   │   ├── models.py             ← all 8 SQLAlchemy models
│   │   ├── logging.py            ← logging setup
│   │   └── app.py                ← FastAPI app factory
│   ├── ingestion/
│   │   └── __init__.py           ← stub
│   ├── analysis/
│   │   └── __init__.py           ← stub
│   ├── trading/
│   │   └── __init__.py           ← stub
│   ├── risk/
│   │   └── __init__.py           ← stub
│   └── dashboard/
│       └── __init__.py           ← stub
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    └── src/
        ├── main.tsx
        └── App.tsx
```

---

## SQLAlchemy 2.x Async Patterns

### Correct 2.x Declarative Syntax

SQLAlchemy 2.x introduced `DeclarativeBase` (replacing `declarative_base()`), `Mapped[T]` type annotations, and `mapped_column()`. All three should be used together. [VERIFIED: docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html]

```python
# trumptrade/core/models.py
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Float, Boolean, Text, Date, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Watchlist(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AppSettings(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # platform post ID
    platform: Mapped[str] = mapped_column(String(20), nullable=False)  # truth_social | twitter
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # SHA-256 dedup
    posted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    raw_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[str] = mapped_column(String(64), nullable=False)  # FK to posts.id
    sentiment: Mapped[str] = mapped_column(String(10), nullable=False)  # BULLISH|BEARISH|NEUTRAL
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    affected_tickers: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    llm_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    keyword_matches: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    final_action: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    reason_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # Alpaca order ID
    signal_id: Mapped[int] = mapped_column(nullable=False)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)  # BUY|SELL
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    mode: Mapped[str] = mapped_column(String(5), nullable=False)  # paper|live
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="submitted")


class Fill(Base):
    __tablename__ = "fills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False)  # FK to orders.id
    fill_price: Mapped[float] = mapped_column(Float, nullable=False)
    fill_qty: Mapped[float] = mapped_column(Float, nullable=False)
    filled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ShadowPortfolioSnapshot(Base):
    __tablename__ = "shadow_portfolio_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    portfolio_name: Mapped[str] = mapped_column(String(20), nullable=False)  # SPY|QQQ|random
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav_value: Mapped[float] = mapped_column(Float, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    positions_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON


class KeywordRule(Base):
    __tablename__ = "keyword_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)   # BULLISH|BEARISH
    override_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.9)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

**What NOT to do:**
- Do NOT use the old `declarative_base()` function — it still works in 2.x but emits deprecation warnings
- Do NOT use `Column(String)` bare without `mapped_column()` — loses type inference
- Do NOT use `relationship()` with lazy loading in async sessions — lazy loads will raise `MissingGreenlet` at runtime. Use `selectinload` or `joinedload` in queries, or mark as `lazy="raise"`

### Async Engine and Session Factory

```python
# trumptrade/core/db.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from trumptrade.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    "sqlite+aiosqlite:///./trumptrade.db",
    echo=settings.debug,          # True in dev, False in prod
    future=True,
)

# expire_on_commit=False is CRITICAL for async — prevents implicit lazy loads after commit
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    """FastAPI dependency — yields a session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

**Key gotcha — `expire_on_commit=False`:** With the default `expire_on_commit=True`, SQLAlchemy expires all loaded attributes after a commit. In a synchronous context, accessing those attributes triggers a lazy SQL SELECT. In an async context, this raises `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called`. Always set `expire_on_commit=False` with async sessions. [VERIFIED: docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html]

**Key gotcha — session per request, not global:** Do not create a single global `AsyncSession()` instance and reuse it across requests. SQLAlchemy sessions are not thread-safe or concurrency-safe. Use `async_sessionmaker` as a factory and create one session per request via the `get_db` dependency. [VERIFIED: docs.sqlalchemy.org - "A single instance of AsyncSession is not safe for use in multiple, concurrent tasks"]

---

## Alembic + Async Engine (Critical Gotcha)

### The Core Problem

Alembic's migration runner is synchronous. When you configure an async SQLAlchemy engine in your app, Alembic cannot use it directly — it needs a sync connection. The solution is to use `async_engine_from_config()` in env.py and call `connection.run_sync()` to bridge back to sync. [VERIFIED: alembic.sqlalchemy.org/en/latest/cookbook.html]

### Step 1: Initialize with the Async Template

```bash
alembic init --template async alembic
```

This generates an `alembic/env.py` pre-configured with the `run_sync` bridge. Do NOT use plain `alembic init alembic` — it generates a sync-only env.py that will fail with aiosqlite.

### Step 2: Configure alembic.ini

```ini
# alembic.ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os

sqlalchemy.url = sqlite+aiosqlite:///./trumptrade.db
```

### Step 3: Wire env.py to Your Models

After `alembic init --template async`, edit the generated `alembic/env.py` to add your model metadata:

```python
# alembic/env.py — key additions only (async template provides the rest)
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# ADD THESE TWO LINES to the generated template:
from trumptrade.core.models import Base  # noqa: F401 — import all models
target_metadata = Base.metadata

# The rest of env.py (do_run_migrations, run_migrations_online, etc.)
# comes from the --template async output — do not hand-roll it.
```

The full canonical async env.py pattern (for reference):

```python
async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())
```

### Step 4: Generate and Run the Migration

```bash
# Generate initial migration (autogenerate from models)
alembic revision --autogenerate -m "initial_schema"

# Apply migration
alembic upgrade head
```

### Step 5: Seed Defaults in the Same Migration

In the generated migration file's `upgrade()` function, add the `app_settings` seed inserts. Use `op.bulk_insert()` or raw `op.execute()`:

```python
# alembic/versions/XXXX_initial_schema.py
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    # ... (table creation code from autogenerate) ...

    # Seed app_settings defaults
    op.execute(
        """
        INSERT INTO app_settings (key, value) VALUES
        ('position_size_pct', '2.0'),
        ('stop_loss_pct', '5.0'),
        ('max_daily_loss_pct', '10.0'),
        ('confidence_threshold', '0.7'),
        ('trading_mode', 'paper'),
        ('bot_enabled', 'false')
        """
    )

def downgrade() -> None:
    # ... (table drop code from autogenerate) ...
```

**Common pitfalls:**

1. **Using plain `alembic init` instead of `--template async`** — generates sync env.py, fails with `sqlite+aiosqlite`
2. **Not importing models in env.py** — autogenerate sees an empty `target_metadata` and generates an empty migration
3. **Circular import when importing Base in env.py** — if `trumptrade/core/db.py` imports from `trumptrade/core/config.py` which does IO, the alembic import chain may fail. Keep `models.py` import-clean (no side effects at module level)
4. **Using `pool.NullPool`** — required for migration scripts to avoid connection pooling interfering with SQLite file locking; already in the async template

[VERIFIED: alembic.sqlalchemy.org cookbook; github.com/sqlalchemy/alembic async template]

---

## FastAPI + APScheduler in One Process

### The Lifespan Pattern (Correct Approach)

FastAPI deprecated `@app.on_event("startup")` in favor of the `lifespan` context manager. Use `lifespan` — it cleanly handles both startup and shutdown in one place. [VERIFIED: fastapi.tiangolo.com/advanced/events/]

```python
# trumptrade/core/app.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler


scheduler = AsyncIOScheduler(timezone="UTC")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    scheduler.start()
    yield
    # SHUTDOWN
    scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    app = FastAPI(
        title="TrumpTrade",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health():
        return {"status": "ok", "scheduler_running": scheduler.running}

    return app
```

**Why `wait=False` on shutdown:** `scheduler.shutdown()` by default waits for running jobs to complete. In a lifespan context with async, this can hang. Use `wait=False` for immediate shutdown; running jobs will be abandoned cleanly.

**Why not `@app.on_event`:** Deprecated since FastAPI 0.93. Still works but triggers deprecation warnings and will eventually be removed.

### The `__main__.py` Entry Point

```python
# trumptrade/__main__.py
import uvicorn
from trumptrade.core.app import create_app


def main():
    """Entry point for both `python -m trumptrade` and the CLI script."""
    app = create_app()
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    main()
```

**Important:** `uvicorn.run()` blocks — it runs the event loop. The APScheduler `AsyncIOScheduler` attaches to the same event loop that uvicorn creates, so the lifespan `scheduler.start()` fires before the first request is accepted. This is the correct integration point. [VERIFIED: WebSearch confirmed, multiple authoritative examples]

**What NOT to do:**
- Do NOT use `uvicorn.run("trumptrade.core.app:app", ...)` with a string import path alongside `create_app()` — the scheduler instance referenced in lifespan will be on a different import path than the one uvicorn loads, causing it to never start. Either pass the app object directly (as above) or use a module-level `app = create_app()` in app.py and use the string path.
- Do NOT call `asyncio.run()` directly in `__main__.py` — uvicorn manages the event loop

### Adding Jobs Later (Phase 3)

Phase 1 just wires the scheduler instance. Phase 3 will add jobs like:

```python
# This goes in Phase 3, NOT Phase 1:
from trumptrade.core.app import scheduler
scheduler.add_job(poll_truth_social, "interval", seconds=90, id="truth_social_poller")
```

Jobs can be added before or after `scheduler.start()`. Adding them before start queues them; adding after start schedules them immediately.

[VERIFIED: apscheduler 3.x docs confirmed via WebSearch; AsyncIOScheduler + lifespan pattern confirmed across multiple 2025 sources]

---

## Pydantic Settings v2

### Correct v2 Pattern

Pydantic v2 replaced `class Config:` with `model_config = SettingsConfigDict(...)`. The old `class Config:` pattern still works (v2 has backward-compat) but emits deprecation warnings. Use the new form. [VERIFIED: pydantic.dev docs, fastapi.tiangolo.com/advanced/settings/]

```python
# trumptrade/core/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Secrets — loaded from .env only
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    x_api_key: str = ""
    x_api_secret: str = ""
    x_bearer_token: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    truth_social_account_id: str = "107780257626128497"

    # Non-secret app config
    debug: bool = False
    db_url: str = "sqlite+aiosqlite:///./trumptrade.db"


@lru_cache
def get_settings() -> Settings:
    """Singleton — called once, cached forever. Override in tests via cache_clear()."""
    return Settings()
```

**The `@lru_cache` singleton pattern:** `Settings()` reads the `.env` file on instantiation. `@lru_cache` on `get_settings()` means the `.env` is read exactly once and the same `Settings` instance is returned on every call. [VERIFIED: fastapi.tiangolo.com/advanced/settings/]

**Usage everywhere in the app:**

```python
from trumptrade.core.config import get_settings

settings = get_settings()
print(settings.alpaca_api_key)
```

**Testing override pattern:**

```python
def test_something(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ALPACA_API_KEY", "test-key")
    # Now get_settings() will re-read env
```

**What NOT to do:**
- Do NOT create `settings = Settings()` at module level in multiple files — each instantiation re-reads the `.env` file and creates a separate instance
- Do NOT use the old `class Config:` form — it works but is deprecated in pydantic-settings v2
- Do NOT put runtime-editable values in Settings — those live in `app_settings` DB table (D-09)

**Design note on two-tier settings (D-08/D-09):** `.env` (via Pydantic Settings) holds only secrets that never change at runtime. Everything the user will edit from the dashboard (`position_size_pct`, `trading_mode`, etc.) lives in the `app_settings` DB table. Downstream phases will implement a `SettingsService` that reads/writes that table via the async session.

[VERIFIED: pydantic.dev/docs/validation/latest/concepts/pydantic_settings/]

---

## Frontend Scaffold (Vite + shadcn/ui)

### Current State (2025/2026)

shadcn/ui updated its setup process with Tailwind CSS v4 in late 2024/early 2025. The new setup is significantly simpler — no `tailwind.config.ts`, no `postcss.config.js`. The CSS entry is a single `@import "tailwindcss"` line. [VERIFIED: ui.shadcn.com/docs/installation/vite, 2026-04-19]

TanStack Query current version: **5.99.1** [VERIFIED: npm view @tanstack/react-query version, 2026-04-19]
Vite current version: **8.0.8** [VERIFIED: npm view vite version, 2026-04-19]
React current version: **19.2.5** [VERIFIED: npm view react version, 2026-04-19]

**Note:** React 19 is now current, not React 18. The CONTEXT.md says React 18 but React 19 is the latest stable release. Since this is a greenfield project, use React 19 unless there's a specific shadcn/ui compatibility concern. shadcn/ui works with React 19.

### Exact Scaffold Commands

```bash
# From the project root (trump_trade/)
# Step 1: Create the Vite project
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install

# Step 2: Install Tailwind v4 (new — no tailwind.config needed)
npm install -D tailwindcss @tailwindcss/vite

# Step 3: Install type aliases support
npm install -D @types/node

# Step 4: Replace src/index.css content
# echo '@import "tailwindcss";' > src/index.css

# Step 5: Update vite.config.ts (see below)

# Step 6: Update tsconfig.json and tsconfig.app.json (see below)

# Step 7: Initialize shadcn/ui
npx shadcn@latest init

# Step 8: Install TanStack Query v5
npm install @tanstack/react-query @tanstack/react-query-devtools
```

### Required Config File Changes

**vite.config.ts:**
```typescript
import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",  // proxy to FastAPI in dev
    },
  },
})
```

**tsconfig.json** (add to compilerOptions):
```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

Apply the same `baseUrl` and `paths` to `tsconfig.app.json`.

### Minimal src/main.tsx with TanStack Query

```typescript
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import "./index.css"
import App from "./App.tsx"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30,  // 30 seconds
      retry: 1,
    },
  },
})

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  </StrictMode>,
)
```

[VERIFIED: ui.shadcn.com/docs/installation/vite; tanstack.com/query/v5/docs/react/quick-start]

**What NOT to do:**
- Do NOT use `--template async` in the shadcn init command — not valid here (that's an Alembic flag)
- Do NOT add `tailwind.config.ts` or `postcss.config.js` — Tailwind v4 does not use them; shadcn/ui's init command handles v4 setup automatically
- Do NOT install `tailwindcss` v3 — the v4 Vite plugin (`@tailwindcss/vite`) is a different package

---

## DB Schema Design

### Table Summary

| Table | Primary Key | Key Columns | Notes |
|-------|------------|-------------|-------|
| `watchlist` | `id` (int) | `ticker` (unique), `added_at` | SETT-01 — bot only trades these tickers |
| `app_settings` | `key` (str) | `value`, `updated_at` | Key-value store for runtime settings |
| `posts` | `id` (str) | `platform`, `content`, `content_hash` (unique), `posted_at` | `content_hash` = SHA-256, dedup gate |
| `signals` | `id` (int) | `post_id`, `sentiment`, `confidence`, `affected_tickers` (JSON) | Full audit: llm_prompt, llm_response, keyword_matches |
| `orders` | `id` (str, Alpaca order ID) | `signal_id`, `ticker`, `side`, `qty`, `mode`, `status` | Bracket order submitted to Alpaca |
| `fills` | `id` (int) | `order_id`, `fill_price`, `fill_qty`, `filled_at` | One row per fill event (handles partials) |
| `shadow_portfolio_snapshots` | `id` (int) | `portfolio_name`, `snapshot_date`, `nav_value`, `cash`, `positions_json` | D-06 spec |
| `keyword_rules` | `id` (int) | `keyword`, `action`, `override_confidence`, `enabled` | Editable from dashboard (Phase 6) |

### Seeded app_settings Values (D-10)

| key | value | Type hint |
|-----|-------|-----------|
| `position_size_pct` | `2.0` | float |
| `stop_loss_pct` | `5.0` | float |
| `max_daily_loss_pct` | `10.0` | float |
| `confidence_threshold` | `0.7` | float |
| `trading_mode` | `paper` | str (paper\|live) |
| `bot_enabled` | `false` | bool (str) |

All values stored as strings; consuming code converts to the correct type. This avoids a polymorphic value column and keeps the table schema simple.

### Design Rationale

**Why `orders` and `fills` are separate (D-07):** Alpaca supports partial fills — an order for 10 shares might fill 5 now and 5 later. If fills were columns on `orders`, partial fills would require updating a row (not append-only). Separate `fills` rows make the audit log purely append-only and match Alpaca's event model exactly.

**Why `content_hash` on `posts`:** Cross-platform deduplication uses SHA-256 of normalized content. Storing the hash in the DB (with a unique constraint) makes dedup a DB-level guarantee, not just an application check. This prevents duplicate LLM calls even if the dedup logic in the ingestion service has a bug.

**Why `app_settings` is key-value:** The values change at runtime via the dashboard. A key-value design means no schema migration is needed to add a new setting — just insert a new row. The trade-off is weaker type safety (all values are strings), which the consuming `SettingsService` handles by converting on read.

---

## Common Pitfalls

### Pitfall 1: `expire_on_commit=True` with AsyncSession
**What goes wrong:** After `session.commit()`, accessing any attribute on a committed object triggers a lazy SELECT. In async context, this raises `MissingGreenlet` because there is no greenlet to run the synchronous lazy load machinery.
**Why it happens:** SQLAlchemy's default session setting expires attributes post-commit as a cache-busting measure. Designed for sync.
**How to avoid:** Always pass `expire_on_commit=False` to `async_sessionmaker`.
**Warning signs:** `sqlalchemy.exc.MissingGreenlet` in stack traces, especially after `await session.commit()`.

### Pitfall 2: Using `alembic init` Without `--template async`
**What goes wrong:** The generated `env.py` uses `engine_from_config()` (sync). When `sqlalchemy.url` uses `sqlite+aiosqlite://`, running `alembic upgrade head` raises `RuntimeError: no running event loop` or a cryptic driver error.
**Why it happens:** aiosqlite is an async driver; it cannot be used with sync SQLAlchemy connection code.
**How to avoid:** Always use `alembic init --template async alembic` for this project.
**Warning signs:** Migration command hangs or crashes with event loop errors.

### Pitfall 3: Forgetting `pip install -e .` After Creating pyproject.toml
**What goes wrong:** `python -m trumptrade` raises `No module named trumptrade` because the package is not on `sys.path`.
**Why it happens:** pyproject.toml alone does not install the package. The package must be installed (even in editable mode) for `python -m` to find it.
**How to avoid:** Run `pip install -e .` from the project root immediately after creating pyproject.toml. Re-run after any structural changes.
**Warning signs:** `ModuleNotFoundError: No module named 'trumptrade'` on first run.

### Pitfall 4: Not Importing All Models in Alembic env.py
**What goes wrong:** `alembic revision --autogenerate` generates an empty migration with no table creations.
**Why it happens:** Alembic inspects `target_metadata` at revision time. If models are not imported (even if `Base.metadata` is correctly pointed at), the metadata is empty because SQLAlchemy registers models into `metadata` only when the model class is loaded.
**How to avoid:** In `alembic/env.py`, import every model module: `from trumptrade.core.models import Base` (this triggers all `class X(Base)` statements). A common pattern is to also add a `from trumptrade.core import models as _models  # noqa: F401` to ensure all models are loaded even if unused directly.
**Warning signs:** Migration file has only `pass` in `upgrade()`.

### Pitfall 5: Lazy Loading Relationships in Async Context
**What goes wrong:** Accessing a relationship attribute (e.g., `post.signals`) outside an async context raises `MissingGreenlet`.
**Why it happens:** SQLAlchemy's default relationship loading strategy (`lazy="select"`) fires a synchronous SELECT. The async session cannot execute this.
**How to avoid:** In Phase 1 there are no relationships, so this is future-proofing: when adding FK relationships, always use `lazy="raise"` on the relationship definition to make the error loud, and use `selectinload(Model.relationship)` in your queries.
**Warning signs:** `MissingGreenlet` when accessing `.attribute` on a model that has a relationship.

### Pitfall 6: shadcn/ui Init Adding Tailwind v3 Config
**What goes wrong:** Running `npx shadcn@latest init` on an older Vite template creates `tailwind.config.ts` and `postcss.config.js`, then breaks when `@tailwindcss/vite` v4 is also installed.
**Why it happens:** If the Vite project was created with an older template that bundled Tailwind v3, there will be version conflicts.
**How to avoid:** Ensure `npm create vite@latest` is used (not a saved template), install `@tailwindcss/vite` (v4) explicitly, and let `npx shadcn@latest init` detect the v4 setup. If shadcn prompts about Tailwind version, select v4.
**Warning signs:** Build errors about conflicting Tailwind plugins, or styles not applying.

---

## Standard Stack (Verified Versions)

### Backend

| Library | Current Version | Purpose | Install |
|---------|----------------|---------|---------|
| `fastapi` | **0.136.0** | Web framework + WebSocket | `pip install fastapi` |
| `uvicorn[standard]` | 0.29+ | ASGI server | `pip install uvicorn[standard]` |
| `pydantic` | 2.7+ | Data validation | included with fastapi |
| `pydantic-settings` | **2.13.1** | Settings from .env | `pip install pydantic-settings` |
| `sqlalchemy[asyncio]` | **2.0.49** | ORM + async core | `pip install sqlalchemy[asyncio]` |
| `aiosqlite` | 0.20+ | Async SQLite driver | `pip install aiosqlite` |
| `alembic` | **1.18.4** | DB migrations | `pip install alembic` |
| `apscheduler` | **3.11.2** | In-process scheduling | `pip install apscheduler` |

[VERIFIED: `pip index versions` against PyPI, 2026-04-19]

### Frontend

| Package | Current Version | Purpose |
|---------|----------------|---------|
| `vite` | **8.0.8** | Build tool / dev server |
| `react` | **19.2.5** | UI framework (note: React 19, not 18) |
| `@tanstack/react-query` | **5.99.1** | Server state management |
| `shadcn/ui` | latest (CLI-managed) | Component library |
| `tailwindcss` | v4 (via `@tailwindcss/vite`) | Styling |

[VERIFIED: `npm view` commands, 2026-04-19]

### Installation

```bash
# Backend (from project root)
pip install -e .

# Frontend (from project root)
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install -D tailwindcss @tailwindcss/vite @types/node
npm install @tanstack/react-query @tanstack/react-query-devtools
npx shadcn@latest init
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Settings from .env | Manual `os.getenv()` calls | `pydantic-settings` `BaseSettings` | Type coercion, validation, test overrides |
| DB migrations | Manual `CREATE TABLE` in code | Alembic `--autogenerate` | Schema drift prevention, rollback support |
| Async session lifecycle | Manual `session.close()` | `async_sessionmaker` context manager | Connection leak prevention |
| Frontend component library | Custom HTML/CSS buttons, tables, inputs | shadcn/ui components | Accessible, themeable, copy-paste — no runtime dep |
| Scheduler in FastAPI | `asyncio.create_task` polling loops | APScheduler `AsyncIOScheduler` | Interval/cron semantics, job IDs, graceful shutdown |
| Config singleton | Module-level `Settings()` repeated everywhere | `@lru_cache` on `get_settings()` | Reads `.env` exactly once; testable via `cache_clear()` |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All backend | Assumed present | Unknown | — |
| Node.js + npm | Frontend scaffold | Assumed present (npm view worked) | npm 8+ | — |
| pip | Python packages | Assumed present | Unknown | — |
| SQLite | DB (via aiosqlite) | Built into Python stdlib | 3.x | — |

Step 2.6: All dependencies are standard tools assumed present. No blocking missing dependencies identified. If `pip install -e .` fails, the user needs Python 3.11+ and pip.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | React 19 is compatible with all shadcn/ui components used in this project | Frontend Scaffold | Minor: some shadcn components may have React 18 peer dep warnings; downgrade to React 18 if needed |
| A2 | APScheduler 3.x `AsyncIOScheduler` attaches to uvicorn's event loop when started in `lifespan` | FastAPI + APScheduler | Medium: scheduler jobs may not fire; fix by passing explicit `event_loop` or using apscheduler 4.x |
| A3 | `alembic init --template async` is available in Alembic 1.18.4 | Alembic section | Low: async template has been available since Alembic 1.7+ |
| A4 | `sqlite+aiosqlite:///./trumptrade.db` creates the DB file in the CWD when app starts | DB section | Low: SQLite creates the file if it doesn't exist; CWD must be project root at startup |

---

## Open Questions

1. **APScheduler 3.x vs 4.x**
   - What we know: APScheduler 4.x (async-first rewrite) was released but has a different API from 3.x. STACK.md specifies 3.x (`apscheduler>=3.10.0`). Current version is 3.11.2.
   - What's unclear: Whether APScheduler 3.x `AsyncIOScheduler` has any known issues with Python 3.12+ or uvicorn's event loop.
   - Recommendation: Stick with 3.x as specified. If scheduler jobs don't fire in integration testing, investigate whether `AsyncIOScheduler` needs an explicit event loop reference in newer Python versions.

2. **React 18 vs React 19**
   - What we know: CONTEXT.md says "React 18" but current npm version is 19.2.5. shadcn/ui supports React 19.
   - What's unclear: Whether the user intentionally wants React 18 specifically.
   - Recommendation: Use React 19 (current stable) for a greenfield project. If any downstream phase runs into React 19 compatibility issues, downgrade is straightforward.

---

## Sources

### Primary (HIGH confidence)
- `docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html` — async engine, async_sessionmaker, expire_on_commit gotcha
- `alembic.sqlalchemy.org/en/latest/cookbook.html` — async migration pattern, run_sync bridge
- `github.com/sqlalchemy/alembic` — async env.py template (--template async)
- `fastapi.tiangolo.com/advanced/events/` — lifespan context manager pattern
- `fastapi.tiangolo.com/advanced/settings/` — @lru_cache get_settings pattern
- `pydantic.dev/docs/validation/latest/concepts/pydantic_settings/` — model_config SettingsConfigDict
- `ui.shadcn.com/docs/installation/vite` — Tailwind v4 + shadcn init steps
- `tanstack.com/query/v5/docs/react/quick-start` — QueryClient setup

### Secondary (MEDIUM confidence)
- WebSearch: APScheduler AsyncIOScheduler + FastAPI lifespan — multiple consistent sources
- WebSearch: pyproject.toml `[project.scripts]` — PyPA docs

### Tertiary (LOW confidence)
- React 19 / shadcn/ui compatibility: based on shadcn's GitHub, not directly verified in this session

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified against PyPI and npm registry
- Architecture patterns: HIGH — verified against official docs for SQLAlchemy, Alembic, FastAPI, Pydantic Settings
- Pitfalls: HIGH — async SQLAlchemy pitfalls verified against official docs; shadcn/Tailwind v4 pitfall verified against current install docs
- Frontend versions: HIGH — verified via npm view (React 19.2.5, Vite 8.0.8, TanStack Query 5.99.1)

**Research date:** 2026-04-19
**Valid until:** 2026-05-19 (stable libraries; re-verify if >30 days pass before implementation)
