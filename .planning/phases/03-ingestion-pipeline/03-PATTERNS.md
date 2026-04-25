# Phase 3: Ingestion Pipeline - Pattern Map

**Mapped:** 2026-04-20
**Files analyzed:** 6 (5 new + 1 modified)
**Analogs found:** 6 / 6

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `trumptrade/ingestion/truth_social.py` | service | event-driven (poll) | `trumptrade/trading/executor.py` | role-match (run_in_executor, AsyncSessionLocal, get_settings) |
| `trumptrade/ingestion/twitter.py` | service | event-driven (poll, sync-in-executor) | `trumptrade/trading/executor.py` | exact (run_in_executor wrapping sync SDK, asyncio.get_running_loop) |
| `trumptrade/ingestion/filters.py` | utility | transform | `trumptrade/trading/executor.py` (stop_price calc) | partial (pure stateless transform logic) |
| `trumptrade/ingestion/heartbeat.py` | service | event-driven (scheduled check) | `trumptrade/trading/executor.py` | role-match (AsyncSessionLocal, get_settings, logger pattern) |
| `trumptrade/ingestion/__init__.py` | package init | — | `trumptrade/trading/__init__.py` | exact (from __future__, re-export pattern) |
| `trumptrade/core/app.py` (modify) | config/factory | — | `trumptrade/core/app.py` itself | exact (local import + register call pattern from Phase 2) |

---

## Pattern Assignments

### `trumptrade/ingestion/truth_social.py` (service, event-driven poll)

**Analog:** `trumptrade/trading/executor.py`

**Imports pattern** (executor.py lines 1–19):
```python
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from trumptrade.core.config import get_settings
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings, Post
from trumptrade.ingestion.filters import apply_filters

logger = logging.getLogger(__name__)
```

**app_settings read pattern** (executor.py lines 119–125):
```python
async def _get_setting(self, key: str) -> str:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings.value).where(AppSettings.key == key)
        )
        return result.scalar_one()  # raises NoResultFound if key missing
```

**app_settings write pattern** (executor.py lines 108–117):
```python
async def set_bot_enabled(self, enabled: bool) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(AppSettings)
            .where(AppSettings.key == "bot_enabled")
            .values(value="true" if enabled else "false")
        )
        await session.commit()
```

**DB session + commit pattern** (executor.py lines 127–143):
```python
async def _log_order(self, ...) -> None:
    async with AsyncSessionLocal() as session:
        session.add(Order(...))
        await session.commit()
```

**config credentials access pattern** (executor.py lines 40–53):
```python
settings = get_settings()
try:
    trading_client = TradingClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        paper=is_paper,
    )
except ValueError as exc:
    raise HTTPException(status_code=502, detail=f"Alpaca credentials not configured: {exc}")
```
For ingestion: replace with `settings.truth_social_account_id` / `settings.x_bearer_token`.

**Error logging pattern** (executor.py lines 66–67, 91–98):
```python
logger.error("Alpaca data API error fetching price for %s: %s", symbol, exc)
```
For ingestion: `logger.error("Truth Social returned %s — may need credentials", resp.status_code)`

**IntegrityError + SAVEPOINT pattern** (from RESEARCH.md Pattern 4 — no existing codebase analog, use research pattern):
```python
from sqlalchemy.exc import IntegrityError

async def _save_post(session: AsyncSession, post: Post) -> bool:
    try:
        async with session.begin_nested():   # SAVEPOINT — keeps outer transaction alive
            session.add(post)
            await session.flush()
        return True
    except IntegrityError:
        logger.debug("Duplicate post skipped: hash=%s", post.content_hash)
        return False
```

---

### `trumptrade/ingestion/twitter.py` (service, event-driven poll, sync-wrapped-in-executor)

**Analog:** `trumptrade/trading/executor.py`

**run_in_executor pattern** (executor.py lines 56–68):
```python
loop = asyncio.get_running_loop()
try:
    trade_map = await loop.run_in_executor(
        None,
        partial(
            data_client.get_stock_latest_trade,
            StockLatestTradeRequest(symbol_or_symbols=symbol),
        ),
    )
except APIError as exc:
    logger.error("Alpaca data API error fetching price for %s: %s", symbol, exc)
    raise HTTPException(status_code=502, detail=f"Alpaca data error: {exc.message}")
```

For twitter.py, adapt to:
```python
loop = asyncio.get_running_loop()
try:
    tweets = await loop.run_in_executor(None, _fetch_twitter_sync, bearer_token, user_id, since_id)
except Exception as exc:
    logger.error("Twitter poll failed: %s", exc)
    return
```

**Sync function pattern** — keep the sync tweepy call in a plain `def`, never `async def`, to keep it safe for `run_in_executor`. Model after the `partial(...)` pattern in executor.py lines 59–64.

**Imports pattern:**
```python
from __future__ import annotations

import asyncio
import logging
from datetime import timezone

import tweepy
from sqlalchemy.exc import IntegrityError

from trumptrade.core.config import get_settings
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings, Post
from trumptrade.ingestion.filters import apply_filters

logger = logging.getLogger(__name__)
```

---

### `trumptrade/ingestion/filters.py` (utility, transform)

**Analog:** None (pure stateless function — no direct analog in codebase). Use RESEARCH.md Pattern (CONTEXT.md D-07/D-08) directly.

**Core pattern** (RESEARCH.md Code Examples — filters.py):
```python
from __future__ import annotations

FINANCIAL_KEYWORDS: frozenset[str] = frozenset({
    "tariffs", "trade", "tax", "stock", "market", "economy", "economic",
    "deal", "sanction", "china", "invest", "dollar", "rate", "inflation",
    "bank", "energy", "oil", "gas", "crypto", "bitcoin", "fed", "reserve",
    "deficit", "debt", "budget", "jobs", "employment", "manufacturing",
    "import", "export",
})

def apply_filters(text: str) -> tuple[bool, str | None]:
    """Return (is_filtered, filter_reason). reason is None when post passes."""
    if len(text) < 100:
        return True, "too_short"
    if text.upper().startswith("RT @"):
        return True, "pure_repost"
    words = set(text.lower().split())
    if not words & FINANCIAL_KEYWORDS:
        return True, "no_financial_keywords"
    return False, None
```

Note: use `frozenset` (not `set`) for `FINANCIAL_KEYWORDS` — it is a module-level constant and frozenset is hashable and slightly faster for membership tests.

---

### `trumptrade/ingestion/heartbeat.py` (service, event-driven scheduled check)

**Analog:** `trumptrade/trading/executor.py`

**Imports pattern:**
```python
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytz
from sqlalchemy import func, select

from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings, Post

logger = logging.getLogger(__name__)
```

**AsyncSessionLocal query pattern** (executor.py lines 119–125 — scalar_one for single value, adapt to scalar for count):
```python
async with AsyncSessionLocal() as session:
    result = await session.execute(
        select(func.count()).select_from(Post)
        .where(Post.platform == "truth_social")
        .where(Post.created_at >= cutoff)
    )
    count = result.scalar()
```

**app_settings read for configurable hours** — read `heartbeat_start_hour` and `heartbeat_end_hour` from `AppSettings` using the same `select(AppSettings.value).where(AppSettings.key == key)` pattern from executor.py lines 121–124. Cast to `int` after fetch; default to 9 and 17 if missing.

**pytz ET window check** (RESEARCH.md Pattern 5):
```python
import pytz

def _is_market_hours(start_hour: int = 9, end_hour: int = 17) -> bool:
    eastern = pytz.timezone("US/Eastern")
    now_et = datetime.now(timezone.utc).astimezone(eastern)
    return start_hour <= now_et.hour < end_hour
```

**WARNING log pattern** (executor.py line 105 shows INFO; same `%s` format for WARNING):
```python
logger.warning("HEARTBEAT: no Truth Social posts in last 30 minutes")
```

---

### `trumptrade/ingestion/__init__.py` (package init, re-export)

**Analog:** `trumptrade/trading/__init__.py` (lines 1–6)

```python
"""Trading package — AlpacaExecutor service and FastAPI router."""
from __future__ import annotations

from trumptrade.trading.router import router as trading_router

__all__ = ["trading_router"]
```

For ingestion, adapt to:
```python
"""Ingestion package — Truth Social, X/Twitter pollers, heartbeat, and job registration."""
from __future__ import annotations

from trumptrade.ingestion.truth_social import poll_truth_social
from trumptrade.ingestion.twitter import poll_twitter
from trumptrade.ingestion.heartbeat import check_heartbeat

def register_ingestion_jobs(scheduler) -> None:
    ...

__all__ = ["register_ingestion_jobs"]
```

**Job registration pattern** (RESEARCH.md Pattern 3 — no codebase analog; use research pattern):
```python
def register_ingestion_jobs(scheduler) -> None:
    scheduler.add_job(
        poll_truth_social,
        trigger="interval",
        seconds=60,
        id="ingestion_truth_social",
        replace_existing=True,
        misfire_grace_time=30,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        poll_twitter,
        trigger="interval",
        minutes=5,
        id="ingestion_twitter",
        replace_existing=True,
        misfire_grace_time=60,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        check_heartbeat,
        trigger="interval",
        minutes=15,
        id="ingestion_heartbeat",
        replace_existing=True,
        misfire_grace_time=120,
        coalesce=True,
        max_instances=1,
    )
```

---

### `trumptrade/core/app.py` (modify — add `register_ingestion_jobs` call)

**Analog:** `trumptrade/core/app.py` itself (lines 56–82) — the Phase 2 local-import pattern is already established.

**Local import + register pattern to copy** (app.py lines 71–72):
```python
# ── Phase 2: trading router ──────────────────────────────────────────────
from trumptrade.trading import trading_router          # local import avoids circular import
app.include_router(trading_router, prefix="/trading", tags=["trading"])
```

For Phase 3, add immediately after the Phase 2 block, still inside `create_app()`:
```python
# ── Phase 3: ingestion jobs ──────────────────────────────────────────────
from trumptrade.ingestion import register_ingestion_jobs   # local import avoids circular import
register_ingestion_jobs(scheduler)
```

The `scheduler` name is already in scope inside `create_app()` via the module-level `scheduler` defined at app.py line 24.

---

## Shared Patterns

### `from __future__ import annotations`
**Source:** Every existing file in the codebase (`executor.py` line 1, `router.py` line 1, `app.py` line 8, `db.py` line 3, `config.py` line 3, `models.py` line 2)
**Apply to:** ALL new ingestion files as the mandatory first line.

### AsyncSessionLocal Session Pattern
**Source:** `trumptrade/trading/executor.py` lines 108–116 and 127–143
**Apply to:** `truth_social.py`, `twitter.py`, `heartbeat.py`
```python
async with AsyncSessionLocal() as session:
    # ... do work ...
    await session.commit()
```
Never use `Depends(get_db)` in service-layer coroutines — that pattern is for FastAPI route handlers only (see `db.py` lines 36–49).

### Logger Initialization
**Source:** `trumptrade/trading/executor.py` line 20, `trumptrade/trading/router.py` line 10
**Apply to:** All new ingestion files
```python
logger = logging.getLogger(__name__)
```

### get_settings() Usage
**Source:** `trumptrade/trading/executor.py` lines 40–41
**Apply to:** `truth_social.py`, `twitter.py`
```python
settings = get_settings()
# then: settings.truth_social_account_id, settings.x_bearer_token
```
`get_settings()` is `@lru_cache` — safe to call at module level or inside functions; returns cached singleton after first call.

### app_settings String Encoding Rule
**Source:** `trumptrade/trading/executor.py` lines 35–37 and line 116
**Apply to:** `truth_social.py`, `twitter.py`, `heartbeat.py`

All `AppSettings.value` reads return raw strings. Cast to target type immediately after read:
```python
stop_loss_pct = float(await self._get_setting("stop_loss_pct"))   # "5.0" → 5.0
# For ingestion:
start_hour = int(value) if value else 9   # "9" → 9, None → default 9
```
All writes must also be string-encoded: `str(count)` for counters, `str(post_id)` for cursors.

### Error-Level Logging for External API Failures
**Source:** `trumptrade/trading/executor.py` lines 66–67, 91–98
**Apply to:** `truth_social.py`, `twitter.py`

Non-200 responses and network errors → `logger.error(...)`, then return empty result (no raise). APScheduler retries on the next tick per D-05.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `trumptrade/ingestion/filters.py` | utility | transform | No stateless pure-function utility files exist yet; use RESEARCH.md Pattern directly |
| IntegrityError + SAVEPOINT pattern | — | — | No existing DB insert with dedup exists; use RESEARCH.md Pattern 4 exactly |
| APScheduler `add_job` calls | — | — | No existing scheduler job registrations in codebase yet; use RESEARCH.md Pattern 3 exactly |

---

## Metadata

**Analog search scope:** `trumptrade/trading/`, `trumptrade/core/`, `trumptrade/ingestion/`
**Files scanned:** 7 (`executor.py`, `router.py`, `app.py`, `db.py`, `config.py`, `models.py`, `trading/__init__.py`)
**Pattern extraction date:** 2026-04-20
