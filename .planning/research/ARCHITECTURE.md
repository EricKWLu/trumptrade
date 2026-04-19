# Architecture Patterns: TrumpTrade

**Domain:** Social-media-signal automated trading bot
**Researched:** 2026-04-19
**Confidence:** HIGH (well-established component patterns for this problem class)

---

## Recommended Architecture

TrumpTrade is an **event-driven pipeline with a polling ingestion layer**. Posts flow in one direction: ingestion → analysis → signal generation → risk evaluation → execution → logging. The web dashboard is a read layer that observes state but does not participate in the trade pipeline.

```
[ Truth Social Poller ]──┐
                          ├──→ [ Deduplication Store ] ──→ [ Analyzer ]
[ X/Twitter Poller ]─────┘                                      │
                                                                 ↓
                                                       [ Signal Generator ]
                                                                 │
                                                                 ↓
                                                        [ Risk Guard ]
                                                                 │
                                                    ┌────────────┴────────────┐
                                                    ↓                         ↓
                                           [ Alpaca Executor ]      [ Shadow Portfolio ]
                                                    │                         │
                                                    └────────────┬────────────┘
                                                                 ↓
                                                          [ Trade Log ]
                                                                 ↑
                                                    [ Web Dashboard (read) ]
```

---

## Component Boundaries

| Component | Responsibility | Owns | Communicates With |
|-----------|---------------|------|-------------------|
| **Truth Social Poller** | Poll public profile page on interval, extract new posts | HTTP session, last-seen post ID | Deduplication Store |
| **X/Twitter Poller** | Poll X API v2 for new posts from target account | X API credentials, last-seen tweet ID | Deduplication Store |
| **Deduplication Store** | Fingerprint posts (hash of normalized text) and reject duplicates across platforms | Post fingerprint cache (SQLite or Redis) | Analyzer |
| **Analyzer** | Call LLM with post text, apply keyword rule layer, emit structured signal | LLM client, keyword rule config | Signal Generator |
| **Signal Generator** | Combine AI confidence + keyword flags into a buy/sell/hold decision per watchlist ticker | Watchlist config | Risk Guard |
| **Risk Guard** | Enforce position size %, stop-loss threshold, max daily loss cap; reject trades that exceed limits | Portfolio state, daily P&L | Alpaca Executor, Shadow Portfolio |
| **Alpaca Executor** | Place orders (paper or live) with attached stop-loss bracket; report fill | Alpaca SDK, mode flag (paper/live) | Trade Log |
| **Shadow Portfolio** | Track what SPY, QQQ, and random-baseline "would have done" for same signals and same entry prices | Shadow P&L state | Trade Log |
| **Trade Log** | Append-only record of every signal, decision, order attempt, fill, and rejection | SQLite database | Web Dashboard |
| **Web Dashboard** | Read-only display of live post feed with analysis, portfolio state, trade history, settings UI | Database reads, settings file | None (read-only) |
| **Settings Store** | Persist watchlist, risk params, mode flag | Config file or DB table | Risk Guard, Signal Generator, Alpaca Executor |

---

## Data Flow: Post to Trade

```
1. INGEST
   Poller detects new post
   → Normalizes text (strip whitespace, lowercase for fingerprint)
   → Queries Dedup Store: "have I seen this fingerprint before?"
     → YES: discard
     → NO: store fingerprint, pass raw post forward

2. ANALYZE
   Post text → LLM prompt → structured response:
     { sentiment: "bullish|bearish|neutral", confidence: 0.0–1.0, reasoning: "..." }
   Keyword rules run on same text:
     { keyword_match: ["tariff", "ban"], override: "bearish", override_confidence: 0.95 }
   Merge: keyword override wins if confidence >= threshold; otherwise AI result stands

3. SIGNAL GENERATION
   For each ticker in watchlist:
     - Map bullish/bearish + confidence to BUY/SELL/HOLD
     - Attach ticker, direction, confidence, source post ID, timestamp

4. RISK CHECK
   For each signal:
     - Is market open? If not → queue or discard (configurable)
     - Would this trade exceed position size %? → reject if yes
     - Is daily loss cap already hit? → halt all trading
     - Compute stop-loss price from current market price + threshold
     - Pass valid trades forward; log rejections with reason

5. EXECUTE
   Mode flag determines target:
     - PAPER: Alpaca paper-api.alpaca.markets
     - LIVE: Alpaca api.alpaca.markets
   Place market order + attached stop-loss bracket order
   Record order ID, fill price, fill time

6. SHADOW PORTFOLIO UPDATE (parallel to execution)
   Same signal, same entry price (from Alpaca market data)
   Apply to SPY shadow, QQQ shadow, random-baseline shadow
   No real orders placed

7. LOG
   Append to trade_log table:
     post_id, platform, post_text, sentiment, confidence, ticker,
     direction, risk_result, order_id, fill_price, fill_time, mode
```

---

## Test Mode vs Live Mode (Architectural Treatment)

**The mode flag is a single configuration value** (`TRADE_MODE = "paper" | "live"`) read at startup by the Alpaca Executor. No other component changes behavior.

```
Settings Store
  └── TRADE_MODE ──→ Alpaca Executor
                        ├── "paper" → paper-api.alpaca.markets
                        └── "live"  → api.alpaca.markets
```

All pipeline stages (ingestion, analysis, signal, risk) behave identically in both modes. This means:
- Paper mode exercises the full real pipeline, including real LLM calls and real risk checks
- The only difference is where orders land
- Dashboard shows current mode prominently to prevent accidental live trading

**Implication for build order:** Build and test the entire pipeline in paper mode first. Adding live mode is a single config value change — no new code paths required.

---

## Comparison / Shadow Portfolio Architecture

Shadow portfolios are **passive observers** that read the same signal stream the executor uses but never touch the Alpaca order API.

```
Signal ──→ Risk Guard ──→ Alpaca Executor    (real/paper orders)
                    └──→ Shadow Engine       (internal accounting only)
                              ├── SPY shadow
                              ├── QQQ shadow
                              └── Random-baseline shadow
```

Shadow Engine design:
- Receives every signal that passes risk guard (same gate as real trades)
- Fetches same-time price from Alpaca market data API (already used for risk calculations)
- Maintains internal position ledger per shadow portfolio
- Compares "what SPY would have done" = buy SPY at same time with same dollar amount
- Random baseline = buy a random S&P 500 constituent each time
- Comparison dashboard: shows actual portfolio P&L vs each shadow over time

The shadow engine can be built after the core trade pipeline since it is purely additive and shares no state with the executor.

---

## Component Build Order

Build order follows data-flow dependencies. Each stage can be tested in isolation before the next is wired.

```
Stage 1 — Foundation (no dependencies)
  ├── Settings Store        (config loader, env vars, watchlist schema)
  ├── Trade Log / Database  (SQLite schema, append + query ops)
  └── Alpaca Executor       (order placement, paper mode only, stub signal input)

Stage 2 — Ingestion (depends on: Log)
  ├── X/Twitter Poller      (X API v2, pagination cursor, dedup fingerprint)
  └── Truth Social Poller   (HTTP scraper, HTML parsing, dedup fingerprint)

Stage 3 — Deduplication (depends on: Pollers)
  └── Dedup Store           (fingerprint cache, cross-platform suppression)

Stage 4 — Analysis (depends on: Dedup Store)
  ├── LLM Analyzer          (prompt engineering, structured output, cost guard)
  └── Keyword Rule Engine   (rule config format, override logic, merge with LLM result)

Stage 5 — Signal + Risk (depends on: Analyzer, Settings, Executor)
  ├── Signal Generator      (per-ticker buy/sell/hold mapping)
  └── Risk Guard            (position sizing, daily loss cap, market hours check)

Stage 6 — Integration (wires all stages)
  └── Orchestrator loop     (scheduler / polling loop that drives the pipeline)

Stage 7 — Observability (depends on: Log, all stages running)
  ├── Web Dashboard         (React or lightweight frontend, read from DB)
  └── Shadow Portfolio Engine

Stage 8 — Live mode (depends on: full paper pipeline validated)
  └── Live mode flag        (config change only, no new code)
```

**Rationale for this order:**
- Alpaca Executor first: gives a real integration point to test against from day one
- Pollers second: scraping/API instability discovered early, not blocked by analysis
- Dedup before analysis: prevents paying LLM costs for duplicate posts
- Risk guard before executor wiring: never accidentally skip risk checks during integration
- Dashboard last: no value until there is data; DB is the source of truth throughout
- Live mode last: paper-validated pipeline is the only safe path to real money

---

## Process Model

Single Python process with a scheduler driving the polling loop.

```
Main process
  ├── APScheduler (or simple asyncio loop) — drives poll intervals
  ├── Poller tasks — run every N seconds
  ├── Pipeline — synchronous chain per new post
  └── Flask / FastAPI server — serves dashboard API on separate thread
```

**Why not microservices?** Single-user tool with no concurrency requirements. Microservices would add deployment complexity with no benefit. If the pipeline becomes slow (LLM latency), async/await on the LLM call is sufficient.

**Why not a queue (Kafka/Redis Streams)?** Over-engineered for the post volume (< 100 posts/day realistic). A simple in-process queue or direct function call chain is correct here. A SQLite-backed queue (post dedup table doubles as queue) is the practical ceiling of needed infrastructure.

---

## State Persistence Model

| State | Storage | Why |
|-------|---------|-----|
| Post fingerprints (dedup) | SQLite table | Persist across restarts, cheap querying |
| Trade log | SQLite table | Append-only, dashboard reads, audit trail |
| Portfolio positions | Alpaca API (source of truth) + local cache | Alpaca owns the real state |
| Shadow portfolio P&L | SQLite table | Need full history for comparison charts |
| Settings / watchlist | JSON config file or SQLite table | Simple, human-editable |
| Daily P&L for loss cap | SQLite table | Reset at market open each day |

Single SQLite database file. No separate database server to run. Sufficient for < 10K rows/day.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Mixing Trading Logic with Scraping Logic
**What goes wrong:** Changes to Truth Social HTML structure break trade execution.
**Instead:** Strict separation — pollers output only normalized `Post` objects. Nothing downstream knows how a post was fetched.

### Anti-Pattern 2: Skipping Risk Guard in "Test" Code Paths
**What goes wrong:** Developer adds a "quick test" shortcut that bypasses risk checks. Code path survives into production.
**Instead:** Risk Guard is the only gate. Paper/live mode is determined after the guard, not before.

### Anti-Pattern 3: Storing Alpaca Credentials in Source Code
**What goes wrong:** Credentials leak via version control.
**Instead:** All credentials (Alpaca keys, X API keys, LLM keys) live in `.env` file, never in code.

### Anti-Pattern 4: Live Mode as a Code Branch
**What goes wrong:** Two divergent code paths for paper and live; bugs fixed in one, not the other.
**Instead:** Mode is a runtime config value consumed only at the Alpaca Executor. One code path.

### Anti-Pattern 5: Polling Too Aggressively on Truth Social
**What goes wrong:** IP ban from scraping too frequently.
**Instead:** 30-60 second minimum poll interval. Randomized jitter (±10s). Respect rate limits.

---

## Scalability Considerations (informational only — personal tool)

| Concern | Current scope | If this grew |
|---------|--------------|--------------|
| Post volume | < 20/day realistic | No concern |
| LLM cost | ~$0.01/post with Claude Haiku | Budget guardrail in config |
| Alpaca rate limits | 200 requests/min | Not a concern at this scale |
| Dashboard concurrent users | 1 | No concern |
| Truth Social scraping blocks | Possible | Rotate user-agent, add jitter |

---

## Sources

- Component boundary patterns: domain knowledge from event-driven trading system design
- Pipeline structure: standard ETL + signal processing pattern adapted for social media input
- Alpaca paper/live mode: Alpaca documentation (paper-api.alpaca.markets vs api.alpaca.markets endpoint separation)
- SQLite for single-user trading tools: well-established pattern in personal trading automation
- Confidence: HIGH for structural patterns; MEDIUM for specific Alpaca endpoint behavior (verify against current Alpaca docs during implementation)
