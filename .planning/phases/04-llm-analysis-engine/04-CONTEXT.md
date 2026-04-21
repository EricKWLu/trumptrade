# Phase 4: LLM Analysis Engine - Context

**Gathered:** 2026-04-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Analyze every qualifying (non-filtered) post from the `posts` table using an LLM + keyword
rule layer, producing a structured signal stored in `signals` with full audit trail.
No new ingestion in this phase — posts arrive via Phase 3 pollers. No execution in this phase
— signals flow to Phase 5 risk guard.

</domain>

<decisions>
## Implementation Decisions

### LLM Provider Architecture
- **D-01:** Provider dispatch is **config-driven via `app_settings`**. Two keys control the
  active LLM: `llm_provider` (default: `"anthropic"`) and `llm_model`
  (default: `"claude-haiku-4-5-20251001"`). Switching providers at runtime = update these
  keys in `app_settings`; the next analysis cycle picks it up automatically. No server restart,
  no code change needed.
- **D-02:** Phase 4 builds **two provider adapters**: Anthropic (primary/default) and Groq
  (free-tier fallback). Each adapter exposes the same `async analyze(text, tickers) -> SignalResult`
  interface. Adding a new provider later = implement the interface in a new file, register it
  in the dispatch map.
- **D-03:** Default provider on fresh install: **Anthropic**, model `claude-haiku-4-5-20251001`.
  Groq adapter uses `llama-3.3-70b-versatile`. Groq API key stored in config as
  `groq_api_key: str = ""` (add to `Settings` in Phase 4). Both keys remain optional — the
  system raises a clear error at analysis time if the active provider's key is missing.
- **D-04:** Structured output strategy:
  - **Anthropic:** Use `tool_use` (tool with input schema) to force JSON structure.
  - **Groq:** Use JSON mode (`response_format={"type": "json_object"}`) + system prompt
    schema instruction.
  - In both cases, output is parsed into a Pydantic `SignalResult` model. Invalid/unparseable
    output: log at ERROR level, skip the post (no signal created), retry on next analysis cycle.

### Analysis Trigger
- **D-05:** A dedicated APScheduler job (`analysis_worker`) polls the `posts` table every
  **30 seconds** for posts where `is_filtered=False` and no corresponding row exists in
  `signals` (LEFT JOIN on `post_id`). Batch size: up to 5 posts per tick to avoid long-running
  jobs. Job registered in Phase 4's `register_analysis_jobs(scheduler)` function, wired into
  `create_app()` via local import (same pattern as ingestion).
- **D-06:** Posts are marked as "analyzed" by the presence of a `signals` row — no new column
  needed on the `posts` table. If a post has an existing signal, it is skipped.

### Prompt Design
- **D-07:** The LLM system prompt is **static** (hardcoded in the analyzer module). The user
  message is **dynamic** and includes:
  1. The post content
  2. The current watchlist tickers (fetched from `watchlist` table at call time, comma-separated)
- **D-08:** LLM is instructed to return ONLY tickers from the provided watchlist. If no watchlist
  ticker is affected, `affected_tickers` must be an empty list. The LLM never invents tickers.
  Pydantic validation enforces this: any returned ticker not in the live watchlist is stripped
  before saving.

### Keyword Rule Layer
- **D-09:** Keyword matching runs AFTER LLM analysis. Matching is case-insensitive substring
  search of post content against `keyword_rules.keyword` (where `is_active=True`).
- **D-10:** Conflict resolution — highest `priority` value wins (higher number = higher priority).
  If multiple rules match at the same priority, the first alphabetically wins (deterministic).
- **D-11:** Rule action semantics:
  - `ignore` → set `final_action = "SKIP"`, `reason_code = "KEYWORD_IGNORE"`. Signal is stored
    but never forwarded to Phase 5.
  - `buy` or `sell` → override LLM sentiment with `BULLISH` (buy) or `BEARISH` (sell). If
    `target_tickers` is set, replace `affected_tickers` with the rule's tickers. If
    `target_tickers` is null, keep LLM's ticker list.
  - If no rule matches, use LLM output unchanged.
- **D-12:** All matching keywords are recorded in `signals.keyword_matches` (JSON array of
  matched keyword strings), even if a higher-priority rule overrides them. Full audit.

### Confidence Gate
- **D-13:** After keyword overlay, if `confidence < 0.7` (read from `app_settings` key
  `confidence_threshold`, defaulting to `"0.7"`):
  - Set `reason_code = "BELOW_THRESHOLD"`
  - Set `final_action = "SKIP"`
  - Signal is stored but never forwarded to Phase 5.
- **D-14:** `SKIP` signals are never forwarded. Only signals with `final_action = "BUY"` or
  `"SELL"` (and `confidence >= 0.7`) are passed to Phase 5.

### Audit Trail
- **D-15:** Every signal stores: `llm_prompt` (full prompt sent), `llm_response` (raw JSON
  string returned), `keyword_matches` (JSON array), `final_action`, `reason_code`. These map
  directly to the existing `Signal` model — no schema changes needed.

### Claude's Discretion
- Exact system prompt wording
- Pydantic `SignalResult` model field names and validators
- Groq API key name in config (`groq_api_key`)
- Batch processing order (oldest-first by `posts.created_at`)
- Error retry behavior (log + skip vs re-queue)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — ANLYS-01 through ANLYS-04 (full text)
- `.planning/ROADMAP.md` §Phase 4 — success criteria SC1–SC4

### Existing Code (read before implementing)
- `trumptrade/core/models.py` — `Signal`, `KeywordRule`, `Post`, `Watchlist`, `AppSettings`
  models (all fields defined; no schema changes needed in Phase 4)
- `trumptrade/core/db.py` — `AsyncSessionLocal` for service-layer DB writes
- `trumptrade/core/config.py` — `anthropic_api_key`, `openai_api_key` already defined;
  add `groq_api_key` in Phase 4
- `trumptrade/core/app.py` — `scheduler` module-level instance; Phase 4 registers
  `analysis_worker` job by calling `register_analysis_jobs(scheduler)` inside `create_app()`
- `trumptrade/analysis/__init__.py` — empty stub; this is the package to build
- `trumptrade/ingestion/__init__.py` — pattern to follow for `register_ingestion_jobs()`

### Stack
- Anthropic: `anthropic` Python SDK — use `client.messages.create()` with `tools=` parameter
  for tool_use structured output
- Groq: `groq` Python SDK (`pip install groq`) — use `client.chat.completions.create()` with
  `response_format={"type": "json_object"}`
- Both are sync SDKs → wrap in `asyncio.get_event_loop().run_in_executor(None, ...)` (same
  pattern as tweepy in Phase 3)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AsyncSessionLocal` — same pattern as ingestion pollers; use `async with AsyncSessionLocal() as session:`
- `get_settings()` — provides all credential fields
- `scheduler` — already running; just add the new job
- `app_settings` DB table — already used for runtime config (Phase 2, 3); add
  `llm_provider`, `llm_model`, `confidence_threshold` keys to seed defaults in migration

### Established Patterns
- `from __future__ import annotations` as first line in every file
- Local import inside `create_app()` to avoid circular imports
- `run_in_executor` for sync SDK calls (Phase 3 twitter.py — reuse this exact pattern)
- `app_settings` read/write: string-encoded; cast to target type after fetch

### Integration Points
- `posts` table — SELECT where `is_filtered=False` and no signal exists (LEFT JOIN)
- `signals` table — INSERT new row per analyzed post
- `keyword_rules` table — SELECT all `is_active=True` rules for keyword matching
- `watchlist` table — SELECT all symbols at prompt-build time
- `app_settings` — read `llm_provider`, `llm_model`, `confidence_threshold`
- `create_app()` — call `register_analysis_jobs(scheduler)` here (local import)

</code_context>

<specifics>
## Specific Ideas

- User wants easy provider switching without subscription lock-in — the `app_settings`
  dispatch approach satisfies this: update `llm_provider` + `llm_model` in the DB and the
  next batch uses the new provider automatically
- Free option built-in from day one: Groq adapter (llama-3.3-70b-versatile) available as
  the free alternative when Anthropic quota is exceeded or subscription lapses

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-llm-analysis-engine*
*Context gathered: 2026-04-21*
