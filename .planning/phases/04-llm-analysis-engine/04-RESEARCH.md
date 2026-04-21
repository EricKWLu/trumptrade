# Phase 4: LLM Analysis Engine - Research

**Researched:** 2026-04-21
**Domain:** LLM structured output, async Python, SQLAlchemy anti-join, APScheduler job registration
**Confidence:** HIGH

## Summary

Phase 4 introduces the analysis layer that converts raw social posts into typed trading signals. Two
provider adapters (Anthropic + Groq) expose a common `async analyze(text, tickers) -> SignalResult`
interface behind a config-driven dispatch map — switching providers is a DB key update with no code
change. Both SDKs are synchronous, so every LLM call is wrapped in `asyncio.get_running_loop().run_in_executor()`,
exactly as the Phase 3 Twitter poller already does.

The analysis worker is an APScheduler interval job (30 s cadence) that queries for up to five
unanalyzed posts via a SQLAlchemy LEFT JOIN anti-join, invokes the active adapter, applies the
keyword rule overlay, gates on confidence threshold, and writes a full audit `Signal` row.
No schema migrations are needed — the `Signal` model already contains every field required.

A key detail: Anthropic forces structure with `tool_use` + `tool_choice={"type": "tool"}` so the
model is guaranteed to emit a `tool_use` block (not prose). The tool input is the structured JSON.
Groq forces structure with `response_format={"type": "json_object"}` on `llama-3.3-70b-versatile`,
which natively supports JSON Object Mode. Both adapters produce an identical `SignalResult` Pydantic
model, invalid fields are stripped, and parse failures are logged + skipped.

**Primary recommendation:** Follow the twitter.py `run_in_executor` pattern exactly. Use `tool_choice={"type": "tool", "name": "classify_post"}` for Anthropic and `response_format={"type": "json_object"}` for Groq. Build one analysis module (`trumptrade/analysis/`) with a dispatcher, two adapters, and a worker job file.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Provider dispatch is config-driven via `app_settings`. Keys: `llm_provider` (default: `"anthropic"`) and `llm_model` (default: `"claude-haiku-4-5-20251001"`). Switching providers = update these keys in `app_settings`; next cycle picks it up automatically.

**D-02:** Two provider adapters: Anthropic (primary/default) and Groq (free-tier fallback). Common interface: `async analyze(text, tickers) -> SignalResult`.

**D-03:** Default model: `claude-haiku-4-5-20251001`. Groq adapter uses `llama-3.3-70b-versatile`. `groq_api_key: str = ""` added to Settings in Phase 4. Missing active-provider key → clear error at analysis time.

**D-04:** Structured output:
- Anthropic: `tool_use` (tool with input schema) + `tool_choice={"type": "tool"}` to force JSON.
- Groq: JSON mode (`response_format={"type": "json_object"}`) + system prompt schema instruction.
- Both: parse into Pydantic `SignalResult`. Unparseable → log ERROR, skip post, retry next cycle.

**D-05:** `analysis_worker` APScheduler job every 30 s. Batch: up to 5 posts where `is_filtered=False` and no `signals` row (LEFT JOIN). Registered via `register_analysis_jobs(scheduler)` in `create_app()` via local import.

**D-06:** "Analyzed" = presence of `signals` row. No new column on `posts`.

**D-07:** System prompt static (hardcoded). User message dynamic: post content + comma-separated watchlist tickers.

**D-08:** LLM returns ONLY tickers from provided watchlist. Pydantic strips any unrecognized ticker.

**D-09:** Keyword matching runs AFTER LLM. Case-insensitive substring search against active `keyword_rules`.

**D-10:** Conflict resolution: highest `priority` wins. Tie: first alphabetically.

**D-11:** Rule action semantics:
- `ignore` → `final_action = "SKIP"`, `reason_code = "KEYWORD_IGNORE"`
- `buy`/`sell` → override LLM sentiment; if `target_tickers` set, replace tickers
- No match → use LLM output unchanged

**D-12:** All matched keywords recorded in `signals.keyword_matches` (JSON array), even if overridden.

**D-13:** After keyword overlay, if `confidence < 0.7` (from `app_settings["confidence_threshold"]`, default `"0.7"`): `reason_code = "BELOW_THRESHOLD"`, `final_action = "SKIP"`.

**D-14:** Only `final_action = "BUY"` or `"SELL"` with confidence >= 0.7 forwarded to Phase 5.

**D-15:** Signal audit fields: `llm_prompt`, `llm_response`, `keyword_matches`, `final_action`, `reason_code` — all present in existing `Signal` model.

### Claude's Discretion
- Exact system prompt wording
- Pydantic `SignalResult` field names and validators
- Groq API key name in config (`groq_api_key`)
- Batch processing order (oldest-first by `posts.created_at`)
- Error retry behavior (log + skip vs re-queue)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ANLYS-01 | LLM classifies each post: sentiment (BULLISH/BEARISH/NEUTRAL), confidence float, affected watchlist tickers | Anthropic tool_use + Groq JSON mode both deliver typed structured output; Pydantic `SignalResult` enforces shape |
| ANLYS-02 | Keyword rule layer that can override or supplement LLM output | Active rules fetched from `keyword_rules` table; priority-ordered overlay logic documented below |
| ANLYS-03 | Discard signals below confidence threshold (default 0.7) — log but never execute | `app_settings["confidence_threshold"]` read at runtime; stored as `SKIP` with `reason_code = "BELOW_THRESHOLD"` |
| ANLYS-04 | Full signal audit: raw LLM prompt, raw LLM response, keyword matches, final action, reason code | `Signal` model already has all columns; worker writes them before committing |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| LLM call dispatch | API/Backend | — | Sync SDK wrapped in executor; no frontend involvement |
| Structured output parsing | API/Backend | — | Pydantic model lives server-side; response never touches browser |
| Keyword rule overlay | API/Backend | — | Pure Python logic on fetched DB rows |
| Confidence gating | API/Backend | — | Single float comparison; no UI interaction in Phase 4 |
| Signal audit write | Database/Storage | API/Backend | SQLAlchemy async session writes `Signal` row |
| Provider config read | API/Backend | Database/Storage | `app_settings` keys read per analysis cycle |
| Job scheduling | API/Backend | — | APScheduler interval job registered in `create_app()` |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `anthropic` | 0.96.0 | Anthropic Claude API client | Official SDK; `tool_use` structured output; sync only → wrap in executor |
| `groq` | 1.2.0 | Groq API client | Official SDK; JSON Object Mode on llama-3.3-70b-versatile |
| `pydantic` | >=2.7.0 (already in deps) | `SignalResult` model + validation | Already in pyproject.toml; v2 model_validator for ticker stripping |

[VERIFIED: npm registry / PyPI] — confirmed via `pip index versions anthropic` → 0.96.0; `pip index versions groq` → 1.2.0

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sqlalchemy[asyncio]` | >=2.0.30 (already in deps) | LEFT JOIN anti-join query, Signal insert | Already installed; used for all DB ops |
| `apscheduler` | >=3.10.0 (already in deps) | 30 s analysis_worker job | Already installed; pattern from ingestion/__init__.py |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Anthropic `tool_use` | Anthropic JSON mode (newer feature) | `tool_use` + `tool_choice={"type":"tool"}` is the battle-tested forced-output pattern; JSON mode is newer and less predictable for strict schema compliance |
| Groq `json_object` | Groq `json_schema` strict mode | `json_object` + system prompt is simpler for the 3-field schema; `json_schema` strict decoding is also supported on llama-3.3-70b-versatile but requires extra schema plumbing |
| Single adapter + provider param | Separate adapter files | Separate files follow the ingestion pattern (truth_social.py / twitter.py) and keep each adapter independently testable |

**Installation (new packages only):**
```bash
pip install "anthropic>=0.96.0" "groq>=1.2.0"
```
Also add to `pyproject.toml` dependencies.

---

## Architecture Patterns

### System Architecture Diagram

```
APScheduler (30 s)
       │
       ▼
analysis_worker()
       │
       ├─ SELECT posts LEFT JOIN signals WHERE signals.id IS NULL
       │  AND is_filtered=False ORDER BY posts.created_at LIMIT 5
       │
       ├─ fetch active watchlist tickers
       │
       ├─ fetch app_settings: llm_provider, llm_model, confidence_threshold
       │
       ▼
  [for each post]
       │
       ├─ build prompt (system + user message with tickers)
       │
       ├─ dispatch to adapter
       │      │
       │      ├─ AnthropicAdapter.analyze()
       │      │    └─ run_in_executor → client.messages.create(tools=[...], tool_choice={"type":"tool"})
       │      │         └─ extract block.input from tool_use block
       │      │
       │      └─ GroqAdapter.analyze()
       │           └─ run_in_executor → client.chat.completions.create(response_format={"type":"json_object"})
       │                └─ json.loads(choices[0].message.content)
       │
       ├─ validate → SignalResult (Pydantic) — strip unknown tickers
       │
       ├─ keyword rule overlay (case-insensitive substring, priority-ordered)
       │
       ├─ confidence gate (< threshold → SKIP)
       │
       └─ INSERT signals row (full audit)
              │
              ▼
         [Phase 5 consumer reads BUY/SELL signals]
```

### Recommended Project Structure
```
trumptrade/analysis/
├── __init__.py          # register_analysis_jobs(scheduler) — mirrors ingestion/__init__.py
├── worker.py            # analysis_worker() async function — main polling loop
├── dispatcher.py        # get_adapter(provider, model) → BaseAdapter
├── base.py              # BaseAdapter ABC + SignalResult Pydantic model
├── anthropic_adapter.py # AnthropicAdapter(BaseAdapter)
└── groq_adapter.py      # GroqAdapter(BaseAdapter)
```

### Pattern 1: Anthropic tool_use for Forced Structured Output

**What:** Pass a single tool with the signal schema, then set `tool_choice={"type": "tool", "name": "classify_post"}` to guarantee the response is always a `tool_use` block (never prose).

**When to use:** Whenever you need schema-guaranteed JSON from Claude; this is the canonical approach used in Anthropic's own docs for forcing structured output.

```python
# Source: https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools

import anthropic
from functools import partial

CLASSIFY_TOOL = {
    "name": "classify_post",
    "description": (
        "Classify a social media post for trading signal generation. "
        "Return sentiment, confidence, and the tickers from the provided watchlist "
        "that are affected by this post. If no watchlist ticker is affected, "
        "return an empty list for affected_tickers."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "sentiment": {
                "type": "string",
                "enum": ["BULLISH", "BEARISH", "NEUTRAL"],
                "description": "Overall market sentiment expressed by the post.",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence score between 0.0 and 1.0.",
            },
            "affected_tickers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Watchlist tickers affected by this post. Empty list if none.",
            },
        },
        "required": ["sentiment", "confidence", "affected_tickers"],
    },
}

def _call_anthropic_sync(api_key: str, model: str, system: str, user: str) -> dict:
    """Sync wrapper — safe to call from run_in_executor."""
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=256,
        system=system,
        tools=[CLASSIFY_TOOL],
        tool_choice={"type": "tool", "name": "classify_post"},
        messages=[{"role": "user", "content": user}],
    )
    # tool_choice={"type":"tool"} guarantees a tool_use block exists
    for block in response.content:
        if block.type == "tool_use":
            return block.input  # already a dict; no json.loads needed
    raise ValueError("No tool_use block in Anthropic response")

async def analyze_anthropic(api_key: str, model: str, system: str, user: str) -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, partial(_call_anthropic_sync, api_key, model, system, user)
    )
```

### Pattern 2: Groq JSON Object Mode

**What:** Pass `response_format={"type": "json_object"}` and instruct the model in the system prompt to return a specific JSON structure. The model is constrained to emit valid JSON.

**When to use:** Groq fallback path; also useful when you want JSON without the tool-call overhead.

```python
# Source: https://console.groq.com/docs/text-chat + https://console.groq.com/docs/model/llama-3.3-70b-versatile
import json
from groq import Groq

def _call_groq_sync(api_key: str, model: str, system: str, user: str) -> dict:
    """Sync wrapper — safe to call from run_in_executor."""
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=256,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return json.loads(response.choices[0].message.content)

async def analyze_groq(api_key: str, model: str, system: str, user: str) -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, partial(_call_groq_sync, api_key, model, system, user)
    )
```

### Pattern 3: run_in_executor (canonical from twitter.py)

Both SDKs are synchronous. Use exactly the same pattern established in Phase 3:

```python
# Source: trumptrade/ingestion/twitter.py (existing codebase)
import asyncio
from functools import partial

loop = asyncio.get_running_loop()
result = await loop.run_in_executor(
    None,                          # default ThreadPoolExecutor
    partial(sync_function, arg1, arg2),
)
```

**Do not use** `asyncio.get_event_loop().run_in_executor()` — `get_event_loop()` is deprecated in Python 3.10+ when called from within a running loop. Use `asyncio.get_running_loop()` instead.

### Pattern 4: SQLAlchemy 2.x Async LEFT JOIN Anti-Join

**What:** Find posts that have no corresponding signal row.

```python
# Source: https://docs.sqlalchemy.org/en/20/tutorial/data_select.html (anti-join pattern)
# Cross-verified: multiple SQLAlchemy community examples
from sqlalchemy import select
from trumptrade.core.models import Post, Signal

stmt = (
    select(Post)
    .outerjoin(Signal, Post.id == Signal.post_id)
    .where(Signal.id.is_(None))          # anti-join: no matching signal
    .where(Post.is_filtered.is_(False))  # only non-filtered posts
    .order_by(Post.created_at.asc())     # oldest-first (deterministic)
    .limit(5)
)
async with AsyncSessionLocal() as session:
    result = await session.execute(stmt)
    posts = result.scalars().all()
```

### Pattern 5: Pydantic v2 SignalResult with Ticker Stripping

```python
# Source: [ASSUMED] — Pydantic v2 model_validator pattern; consistent with Pydantic 2.x docs
from pydantic import BaseModel, model_validator
from typing import Literal

class SignalResult(BaseModel):
    sentiment: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    confidence: float
    affected_tickers: list[str]

    @model_validator(mode="after")
    def strip_invalid_tickers(self) -> "SignalResult":
        """Populated after __init__; strip tickers not in allowlist.

        Note: allowlist must be injected before validation. Pattern: subclass or
        pass via model_config, or strip in the worker after parse.
        """
        # Stripping happens in worker, not here, because allowlist is runtime data.
        # Worker calls: result.affected_tickers = [t for t in result.affected_tickers if t in live_tickers]
        return self
```

**Key insight:** Ticker stripping is simplest as a post-parse filter in the worker (not a Pydantic validator), because the live watchlist is fetched at runtime, not available at class-definition time.

### Pattern 6: Keyword Rule Overlay

```python
# Source: [ASSUMED] — standard Python pattern; logic fully specified in D-09 through D-12
from trumptrade.core.models import KeywordRule

async def _get_active_rules(session) -> list[KeywordRule]:
    result = await session.execute(
        select(KeywordRule)
        .where(KeywordRule.is_active.is_(True))
        .order_by(KeywordRule.priority.desc(), KeywordRule.keyword.asc())
    )
    return result.scalars().all()

def apply_keyword_overlay(
    content: str,
    rules: list[KeywordRule],
    signal: SignalResult,
) -> tuple[str, str | None, list[str], list[str]]:
    """Returns (final_action, reason_code, affected_tickers, keyword_matches)."""
    matched: list[KeywordRule] = [
        r for r in rules if r.keyword.lower() in content.lower()
    ]
    keyword_matches = [r.keyword for r in matched]

    if not matched:
        # No rule hit — use LLM output
        action = "BUY" if signal.sentiment == "BULLISH" else (
            "SELL" if signal.sentiment == "BEARISH" else "SKIP"
        )
        return action, None, signal.affected_tickers, keyword_matches

    # Highest priority rule wins (already sorted by priority DESC, keyword ASC)
    winner = matched[0]

    if winner.action == "ignore":
        return "SKIP", "KEYWORD_IGNORE", signal.affected_tickers, keyword_matches

    action = "BUY" if winner.action == "buy" else "SELL"
    sentiment_override = "BULLISH" if winner.action == "buy" else "BEARISH"
    signal.sentiment = sentiment_override  # mutate in place

    import json
    tickers = (
        json.loads(winner.target_tickers)
        if winner.target_tickers
        else signal.affected_tickers
    )
    return action, None, tickers, keyword_matches
```

### Anti-Patterns to Avoid

- **Calling `client.messages.create()` directly in an async function without run_in_executor:** Both `anthropic.Anthropic` and `groq.Groq` are synchronous clients. Calling them directly blocks the uvicorn event loop. Use the async variants (`anthropic.AsyncAnthropic`, `groq.AsyncGroq`) if available, or always wrap sync clients in `run_in_executor`.
- **Using `asyncio.get_event_loop()` inside an async function:** Deprecated in Python 3.10+. Use `asyncio.get_running_loop()`.
- **Instantiating SDK clients once at module level with `lru_cache`:** API keys come from `get_settings()` which is fine to cache, but the client object itself holds a connection pool. Module-level client is acceptable for a single-user app, but instantiate inside the sync wrapper to avoid cross-thread issues in the executor.
- **Not handling Anthropic response where `stop_reason != "tool_use"`:** When `tool_choice={"type":"tool"}` is set, this should not happen, but defensive code should still check `block.type == "tool_use"` before accessing `block.input`.
- **Trusting LLM to return only watchlist tickers:** Always strip post-parse, even with explicit instructions. The Pydantic model validates shape; the worker validates business rules.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured LLM output | Custom prompt + regex parsing | Anthropic `tool_use` / Groq `json_object` | SDK-enforced schemas prevent malformed output; regex breaks on edge cases |
| Async execution of sync SDK | `threading.Thread` + event | `asyncio.get_running_loop().run_in_executor()` | Already established pattern in twitter.py; thread pool managed by asyncio |
| LLM response validation | Manual dict key checks | Pydantic `SignalResult` with `model_validate()` | Handles missing fields, type coercion, and provides clear error messages |
| SQL anti-join | Python-side set subtraction | SQLAlchemy `.outerjoin(...).where(Signal.id.is_(None))` | DB-side filter; scales to any post count |

**Key insight:** LLM output parsing is the highest-risk custom code surface. Use SDK-level schema enforcement (tool_use / json_object) as the first line of defense, then Pydantic as the second. Never trust raw LLM output.

---

## Common Pitfalls

### Pitfall 1: Anthropic `block.input` Is Already a Dict
**What goes wrong:** Developer calls `json.loads(block.input)` — raises `TypeError` because `block.input` from a `tool_use` block is already a Python `dict`, not a JSON string.
**Why it happens:** Anthropic SDK deserializes the tool input automatically.
**How to avoid:** Use `block.input` directly with Pydantic: `SignalResult.model_validate(block.input)`.
**Warning signs:** `TypeError: the JSON object must be str, bytes or bytearray, not dict`.

### Pitfall 2: Groq `response.choices[0].message.content` Is a JSON String
**What goes wrong:** Developer tries to use `message.content` as a dict — raises `TypeError`.
**Why it happens:** Groq returns JSON-encoded text, not a dict. Different from Anthropic's `block.input`.
**How to avoid:** Always `json.loads(response.choices[0].message.content)` before `model_validate()`.
**Warning signs:** `TypeError: 'str' object is not subscriptable`.

### Pitfall 3: Missing `asyncio.get_running_loop()` in Async Context
**What goes wrong:** `asyncio.get_event_loop()` raises `DeprecationWarning` in Python 3.10+ and may return a different loop than the running one.
**Why it happens:** Python 3.10 deprecated `get_event_loop()` in running-async contexts.
**How to avoid:** Use `loop = asyncio.get_running_loop()` at the top of any async function that needs to call `run_in_executor`.
**Warning signs:** `DeprecationWarning: There is no current event loop`.

### Pitfall 4: Keyword Substring Match Is Case-Sensitive
**What goes wrong:** Keyword rule "tariffs" misses post containing "TARIFFS" or "Tariffs".
**Why it happens:** `r.keyword in content` is case-sensitive.
**How to avoid:** Always `r.keyword.lower() in content.lower()` (D-09 explicitly requires case-insensitive).
**Warning signs:** Rules never fire on real posts; unit tests pass with exact-case inputs only.

### Pitfall 5: LEFT JOIN Fetches Duplicate Posts
**What goes wrong:** If a post has multiple signals (shouldn't happen given the logic, but if code has a bug), the same post appears multiple times in the batch.
**Why it happens:** `outerjoin()` without `distinct()` can produce multiple rows.
**How to avoid:** Add `.distinct()` to the SELECT or rely on the fact that the anti-join `Signal.id.is_(None)` condition naturally excludes posts that have any signal. Either approach is safe.
**Warning signs:** Same post analyzed twice; `IntegrityError` on Signal insert (post_id not unique-constrained but logic expects one signal per post).

### Pitfall 6: `app_settings` Read Must Happen Per-Cycle, Not at Module Load
**What goes wrong:** Provider is switched in the DB but the analyzer still uses the cached provider from startup.
**Why it happens:** Reading `llm_provider` at module import time vs. per-cycle.
**How to avoid:** Read `llm_provider`, `llm_model`, and `confidence_threshold` from the DB at the start of each `analysis_worker()` invocation (D-01 requirement: "next analysis cycle picks it up automatically").
**Warning signs:** Provider switch has no effect without restarting the server.

---

## Code Examples

### Anthropic Adapter Full Pattern

```python
# Source: https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools + handle-tool-calls
from __future__ import annotations

import asyncio
from functools import partial

import anthropic


CLASSIFY_TOOL_DEF = {
    "name": "classify_post",
    "description": (
        "Classify a Trump social media post for trading signal generation. "
        "Return the market sentiment, your confidence score, and ONLY the tickers "
        "from the provided watchlist that are materially affected by this post. "
        "If no watchlist ticker is affected, return an empty list."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "sentiment": {
                "type": "string",
                "enum": ["BULLISH", "BEARISH", "NEUTRAL"],
            },
            "confidence": {"type": "number"},
            "affected_tickers": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["sentiment", "confidence", "affected_tickers"],
    },
}


def _anthropic_call_sync(api_key: str, model: str, system: str, user_msg: str) -> dict:
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=256,
        system=system,
        tools=[CLASSIFY_TOOL_DEF],
        tool_choice={"type": "tool", "name": "classify_post"},
        messages=[{"role": "user", "content": user_msg}],
    )
    for block in response.content:
        if block.type == "tool_use":
            return block.input  # dict, not a JSON string
    raise ValueError(f"Anthropic: no tool_use block in response (stop_reason={response.stop_reason})")
```

### Groq Adapter Full Pattern

```python
# Source: https://console.groq.com/docs/text-chat
from __future__ import annotations

import asyncio
import json
from functools import partial

from groq import Groq


def _groq_call_sync(api_key: str, model: str, system: str, user_msg: str) -> dict:
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=256,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
    )
    raw = response.choices[0].message.content  # JSON string
    return json.loads(raw)                      # must parse explicitly
```

### Worker Anti-Join Query Pattern

```python
# Source: https://docs.sqlalchemy.org/en/20/tutorial/data_select.html
from sqlalchemy import select
from trumptrade.core.models import Post, Signal
from trumptrade.core.db import AsyncSessionLocal

async def _fetch_unanalyzed_posts(limit: int = 5) -> list[Post]:
    stmt = (
        select(Post)
        .outerjoin(Signal, Post.id == Signal.post_id)
        .where(Signal.id.is_(None))
        .where(Post.is_filtered.is_(False))
        .order_by(Post.created_at.asc())
        .limit(limit)
    )
    async with AsyncSessionLocal() as session:
        result = await session.execute(stmt)
        return result.scalars().all()
```

### `register_analysis_jobs` Pattern

```python
# Source: trumptrade/ingestion/__init__.py (existing codebase — mirror exactly)
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from trumptrade.analysis.worker import analysis_worker


def register_analysis_jobs(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        analysis_worker,
        trigger="interval",
        seconds=30,
        id="analysis_worker",
        replace_existing=True,
        misfire_grace_time=15,
        coalesce=True,
        max_instances=1,
    )


__all__ = ["register_analysis_jobs"]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| OpenAI function_calling (legacy) | `tool_use` with `tool_choice={"type":"tool"}` on Anthropic | 2024 | Guaranteed tool invocation; Claude never bypasses with prose |
| `asyncio.get_event_loop()` | `asyncio.get_running_loop()` | Python 3.10 | Required when already inside async context |
| Groq SDK <1.0 (OpenAI shim only) | `groq` SDK >=1.0 (native client) | 2024 | `groq.Groq` is now a first-class client; identical interface to OpenAI but separate package |

**Deprecated/outdated:**
- `asyncio.get_event_loop()`: Raises DeprecationWarning in Python 3.10+ when called from within a running event loop. Use `asyncio.get_running_loop()`.
- Anthropic `completions` API (pre-Messages API): Do not use. All new code uses `client.messages.create()`.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `block.input` from Anthropic tool_use block is a `dict` (not JSON string) | Code Examples | If it's a string, `model_validate()` will fail — fix is trivial: add `json.loads()` |
| A2 | Pydantic ticker stripping done post-parse in worker (not via model_validator) is the simplest approach | Pattern 5 | Alternative: pass tickers as context and use model_validator — more complex but equivalent |
| A3 | Groq `llama-3.3-70b-versatile` supports `response_format={"type": "json_object"}` | Standard Stack | Verified via official docs; risk is near-zero |

---

## Open Questions

1. **AsyncAnthropic vs sync + executor**
   - What we know: The `anthropic` SDK provides both `Anthropic` (sync) and `AsyncAnthropic` (async) clients [CITED: anthropic SDK PyPI page].
   - What's unclear: The CONTEXT.md specifies sync + executor (matching twitter.py). `AsyncAnthropic` would eliminate the executor wrapper.
   - Recommendation: Follow D-04 exactly — use sync + `run_in_executor` for consistency with twitter.py. Consider `AsyncAnthropic` only if latency becomes a concern.

2. **Groq `json_schema` strict mode vs `json_object` mode**
   - What we know: Groq docs show both modes on llama-3.3-70b-versatile. `json_schema` strict mode uses constrained decoding for guaranteed schema compliance.
   - What's unclear: Whether strict mode has different token overhead or latency characteristics.
   - Recommendation: Use `json_object` as decided in D-04. `json_schema` strict is an upgrade path if `json_object` produces off-schema outputs.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `anthropic` pip package | Anthropic adapter | ✗ (not in pyproject.toml yet) | 0.96.0 available | — (must install) |
| `groq` pip package | Groq adapter | ✗ (not in pyproject.toml yet) | 1.2.0 available | — (must install) |
| `ANTHROPIC_API_KEY` env var | Anthropic adapter at runtime | Unknown | — | Clear error at analysis time (D-03) |
| `GROQ_API_KEY` env var | Groq adapter at runtime | Unknown | — | Clear error at analysis time (D-03) |
| `trumptrade/analysis/__init__.py` | analysis package | ✓ (stub exists) | — | — |

**Missing dependencies with no fallback:**
- `anthropic` and `groq` Python packages — must be added to `pyproject.toml` and installed before implementation.

**Missing dependencies with fallback:**
- API keys — system raises a clear runtime error if the active provider's key is missing (not a startup blocker; defaults to Anthropic, so only `ANTHROPIC_API_KEY` is required for default operation).

---

## Sources

### Primary (HIGH confidence)
- Anthropic official docs (platform.claude.com/docs) — tool_use define-tools, handle-tool-calls, models overview; `claude-haiku-4-5-20251001` confirmed as valid current model ID
- Groq official docs (console.groq.com/docs) — llama-3.3-70b-versatile capabilities confirmed; JSON Object Mode confirmed supported
- PyPI registry — `anthropic` 0.96.0 (latest), `groq` 1.2.0 (latest) confirmed via `pip index versions`
- Existing codebase — `trumptrade/ingestion/twitter.py` run_in_executor pattern, `trumptrade/ingestion/__init__.py` job registration pattern

### Secondary (MEDIUM confidence)
- SQLAlchemy 2.0 docs anti-join pattern: `.outerjoin().where(Signal.id.is_(None))` — confirmed via official SQLAlchemy docs and cross-validated by multiple community examples

### Tertiary (LOW confidence)
- None — all claims verified via primary or secondary sources.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — package versions verified via PyPI; model IDs verified via official Anthropic docs; Groq model capabilities verified via official Groq docs
- Architecture: HIGH — patterns directly from existing codebase (twitter.py, ingestion/__init__.py) and official SDK docs
- Pitfalls: HIGH — items 1–3 verified against SDK docs; items 4–6 derived from existing codebase patterns and D-decisions in CONTEXT.md

**Research date:** 2026-04-21
**Valid until:** 2026-07-21 (stable SDKs; Anthropic model IDs are versioned snapshots and won't change)
