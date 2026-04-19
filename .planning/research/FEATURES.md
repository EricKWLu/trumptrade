# Feature Landscape

**Domain:** Automated political-signal trading bot (single-user, social media → trade execution)
**Project:** TrumpTrade
**Researched:** 2026-04-19
**Confidence:** MEDIUM — external web tools unavailable; based on training knowledge (cutoff Aug 2025) of Alpaca API, algo trading dashboard conventions, and social-signal trading patterns. Core Alpaca capabilities are stable and well-documented.

---

## Table Stakes

Features users expect. Missing any of these makes the product feel broken or unusable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Signal ingestion — Truth Social polling | Core product premise; missing it = half the signal source gone | Med | No official API; HTTP scraping of public profile. Fragile by nature. Must handle rate limits, HTML changes, and bot detection gracefully. |
| Signal ingestion — X/Twitter API | He cross-posts; missing it = missed signals | Low-Med | X Basic API ($100/mo) provides filtered stream or search endpoint. Well-understood integration. |
| Post deduplication | Same post on both platforms must not trigger two trades | Low | Hash or normalized-text comparison. If skipped, risk doubles on every cross-posted signal. |
| LLM sentiment classification | Raw post text → (bullish/bearish/neutral, confidence score) | Med | Single LLM call per post. Must output structured JSON. Prompt engineering matters — "DJT just listed as a buy" vs "everyone should buy DJT" are very different. |
| Keyword rule layer | Hard override / fallback when LLM is ambiguous or down | Low | Simple dictionary: {"tariff": bearish, "deal": bullish, etc.}. Runs before OR after LLM depending on design. Prevents LLM hallucination from causing bad trades. |
| Paper trading mode | Non-negotiable for any trading bot. No paper mode = cannot test safely | Low | Alpaca provides a full paper environment at `paper-api.alpaca.markets`. Same API surface as live. Free. Must be the DEFAULT mode. |
| Live trading mode toggle | The actual value delivery of the product | Low | Switch Alpaca base URL + credentials. Must require explicit confirmation to enable. |
| User-defined watchlist | Controls which tickers the bot touches | Low | Stored config. Tickers not on list must never be traded. Missing = bot buys anything it infers. |
| Position sizing (% of portfolio) | Without it, every trade risks the whole account | Low | e.g., "max 5% of portfolio per signal". Required for any rational risk management. |
| Stop-loss per trade | Automatic downside cap per position | Low | Alpaca supports bracket orders (entry + stop + take-profit in one order). Must attach to every market order. |
| Max daily loss cap (kill switch) | Prevents catastrophic loss from a bad signal day | Med | Bot checks daily P&L before each trade; halts if threshold breached. Requires tracking realized + unrealized loss. |
| Live post feed on dashboard | See what triggered a trade | Low | Websocket or polling refresh. Posts + parsed sentiment displayed in chronological order. |
| Trade log | See what the bot did and why | Low | Table: timestamp, ticker, direction, size, entry price, exit price, P&L, triggering post excerpt. |
| Portfolio / positions view | Current open positions, unrealized P&L | Low | Pulled from Alpaca `/v2/positions`. Refreshed on interval. |
| Bot on/off control | Hard stop without killing the server | Low | Toggle in dashboard that pauses signal → trade pipeline. State stored in DB/config. |
| Error / alert visibility | Know when scraping breaks, API fails, or LLM errors | Med | Dashboard banner or log panel showing last N errors. Missing = bot silently fails. |

---

## Differentiators

Features that create meaningful advantage for this specific use case. Not expected by default, but add real value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Benchmark comparison portfolios (SPY, QQQ, random baseline) | Answers "is my bot actually adding alpha?" — the hardest question in personal algo trading | Med | Three shadow portfolios that make the same capital allocation decisions as if they had bought SPY, QQQ, or a random ticker on each signal day. All tracked via Alpaca historical price data. Requires careful same-period normalization. |
| Confidence threshold gate | Only trade when LLM confidence exceeds N% — filters weak signals | Low | Single config value. Dramatically reduces noise trades. Without it, every ambiguous post triggers a trade. |
| Signal-to-trade audit trail | See exactly: post text → LLM raw response → keyword match → decision made → order sent | Med | Critical for debugging bad trades and tuning the model. Not typically built in v1 of trading bots but pays dividends immediately. |
| Post relevance filter | Skip posts that are clearly off-topic (birthday wishes, sports scores) before LLM analysis | Low | Saves LLM API cost and reduces false signal rate. Simple keyword/length heuristic or cheap classifier. |
| Duplicate-within-window suppression | Same signal (e.g., "tariffs!") posted 3x in 1 hour = 1 trade, not 3 | Low | Time-windowed dedup on signal intent, not just post text. Prevents over-trading on a theme. |
| Watchlist-to-signal mapping | Optionally pre-associate tickers with keywords ("steel" → X, Y, Z) so signal routing is explicit | Med | Moves beyond "trade everything on watchlist" to "trade the tickers most relevant to this signal type". Higher precision. |
| Manual trade override panel | Force-buy or force-sell a position directly from the dashboard | Med | Needed when bot misclassifies and user wants to correct without switching to brokerage UI. Requires Alpaca order submission from frontend via backend API. |
| Polling interval configurability | Tune scraping frequency without code changes | Low | Config value exposed in settings UI. Low complexity but meaningful for managing rate-limit risk. |

---

## Anti-Features

Things to deliberately NOT build in v1. Scope creep killers.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Multi-source signal aggregation (Reddit, news, other politicians) | Turns a focused tool into an unfocused one. Signal quality degrades when sources conflict. | Lock to Trump on Truth Social + X. Add sources only after v1 is proven. |
| Custom user-defined comparison strategies | Arbitrary strategy comparison requires a backtesting engine. Out of scope. | Ship the three fixed benchmarks (SPY, QQQ, random). That answers the core question. |
| WebSocket real-time tweet streaming | X streaming API requires Elevated access ($). Truth Social has no streaming. Polling at 30-60s intervals is sufficient for "faster than a human". | Use polling. Revisit only if latency proves to be a user complaint. |
| Portfolio rebalancing / position management logic | Deciding when to EXIT based on portfolio drift is a separate problem from signal-triggered entry. Complex. | Use fixed stop-loss + optional take-profit via Alpaca bracket orders. No dynamic rebalancing. |
| Multi-user support / authentication | This is a personal tool. Auth adds significant complexity for zero current benefit. | Single-user. No login page. Restrict to localhost or VPN if needed. |
| Mobile app | Web dashboard at desktop size is sufficient for monitoring and control. | Responsive web is a nice-to-have; native mobile is not. |
| Backtesting against historical posts | Requires a historical corpus of Trump posts with timestamps AND historical prices. Data acquisition is a project in itself. | Paper trading is the testing mechanism. Log data now; build backtesting later if desired. |
| Options trading | Adds complexity: expiry management, greeks, assignment risk. Alpaca does support options but the risk surface is enormous for an automated bot. | Equities only in v1. |
| Tax lot optimization | Wash sale tracking, FIFO vs LIFO — accounting-level complexity. | Out of scope entirely. User handles their own taxes. |
| Notification push (SMS/email/Slack) | Adds external service dependencies. Dashboard + trade log is the notification mechanism. | If added later, one integration (e.g., Discord webhook) is low complexity and sufficient. |

---

## Feature Dependencies

```
Truth Social polling          ──┐
X/Twitter API ingestion       ──┤── Post deduplication ──► Post relevance filter ──► LLM sentiment analysis
                                                                                               │
                                                                                    Keyword rule layer (override)
                                                                                               │
                                                                              Confidence threshold gate
                                                                                               │
                                                              ┌────────────────────────────────┘
                                                              │
                                              ┌───────────────▼──────────────┐
                               Paper mode ────►   Trade execution engine     ◄──── Live mode toggle
                                              │  (Alpaca API, bracket order) │
                                              └───────────┬──────────────────┘
                                                          │
                              Position sizing ────────────┤
                              Stop-loss config ───────────┤
                              Max daily loss cap ──────────┤
                              Watchlist filter ────────────┘
                                                          │
                                              ┌───────────▼──────────────────┐
                                              │        Trade log + DB         │
                                              └───────────┬──────────────────┘
                                                          │
                              ┌───────────────────────────▼─────────────────────────────┐
                              │                     Web Dashboard                        │
                              │  Live post feed │ Trade log │ Portfolio view │ Settings  │
                              │  Bot on/off     │ Error log │ Benchmark comparison       │
                              └─────────────────────────────────────────────────────────┘

Benchmark comparison portfolios depend on: Trade log (same timestamps), Alpaca historical price data
Signal-to-trade audit trail depends on: Trade log + LLM raw response storage
Manual trade override depends on: Dashboard + backend API + Alpaca order submission
```

---

## MVP Recommendation

**Build in this order (each item unblocks the next):**

1. **Alpaca paper trading integration** — establish the execution foundation first. Proves the broker connection before touching signals.
2. **X/Twitter ingestion** — more reliable than Truth Social (official API). Validate the ingestion-to-trade pipeline end-to-end.
3. **LLM sentiment analysis + keyword rules** — core signal intelligence. Can be tested against static post fixtures before wiring to live feed.
4. **Trade execution with position sizing + stop-loss** — complete the end-to-end loop in paper mode.
5. **Max daily loss cap** — safety gate before live mode is even considered.
6. **Truth Social scraping** — add second ingestion source with deduplication. More fragile, add after pipeline is proven.
7. **Web dashboard** — post feed, trade log, portfolio view, bot toggle, settings. Once the backend works, the dashboard is display and control only.
8. **Benchmark comparison portfolios** — layered on top of existing trade log data. No new backend logic needed, just shadow portfolio calculation.
9. **Live trading mode** — explicit toggle with confirmation. Enable only after paper trading demonstrates acceptable performance.

**Defer to later milestone:**
- Signal-to-trade audit trail (valuable but not MVP-blocking — add once pipeline is stable)
- Manual trade override panel (useful but dashboard is read-only in v1)
- Post relevance filter (optimization; the confidence threshold gate provides similar protection)
- Watchlist-to-signal mapping (enhancement over the simpler "trade all watchlist tickers" approach)

---

## Risk Notes by Feature

| Feature | Risk | Severity |
|---------|------|----------|
| Truth Social scraping | Site structure changes break scraping silently | HIGH — needs health-check monitoring |
| LLM sentiment analysis | Hallucination or ambiguity causes wrong signal direction | HIGH — keyword override layer is the mitigation |
| Max daily loss cap | Off-by-one in P&L calculation leaves bot running after limit | HIGH — must be tested explicitly in paper mode |
| Live trading toggle | Accidental enable during testing | MED — require two-step confirmation |
| Post deduplication | Cross-platform hash collision misses a real duplicate | LOW — tolerable rare occurrence |
| Benchmark comparison | Incorrect time-period alignment makes comparison meaningless | MED — careful normalization required |

---

## Sources

- Alpaca Markets API documentation (training knowledge, cutoff Aug 2025) — HIGH confidence for order types, paper environment, bracket orders
- General algo trading dashboard conventions (training knowledge) — HIGH confidence for table stakes features
- Social media signal trading patterns (training knowledge) — MEDIUM confidence; this specific niche (political figure → equity signal) is less well-documented than general sentiment trading
- PROJECT.md requirements (provided) — used as primary scope constraint throughout

**Confidence by section:**
- Table stakes: HIGH (these are universal to any trading bot)
- Differentiators: MEDIUM-HIGH (specific to this use case; judgment-based)
- Anti-features: HIGH (scope decisions grounded in PROJECT.md out-of-scope list)
- Dependencies: HIGH (logical dependencies, not empirically researched)
- Risk notes: MEDIUM (based on known fragility patterns for scraping + LLM pipelines)
