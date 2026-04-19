# Requirements: TrumpTrade

**Defined:** 2026-04-19
**Core Value:** Automatically detect and act on Trump's social media posts faster than a human can react — turning his words into trade signals before the market moves.

## v1 Requirements

### Ingestion

- [ ] **INGEST-01**: System polls Truth Social for new Trump posts on a schedule with a heartbeat alert when zero posts are seen during a daytime window
- [ ] **INGEST-02**: System polls Trump's X/Twitter account for new posts with rate-limit budget tracking and retry on limit headers
- [ ] **INGEST-03**: System deduplicates posts across platforms using SHA-256 content hash before any signal is routed
- [ ] **INGEST-04**: System pre-filters posts for relevance (skips short posts, pure reposts, and posts with no financial keywords) before calling LLM

### Analysis

- [ ] **ANLYS-01**: System classifies each post via LLM producing structured output: sentiment (BULLISH/BEARISH/NEUTRAL), confidence float, and list of affected watchlist tickers
- [ ] **ANLYS-02**: System applies keyword rule layer that can override or supplement LLM output (e.g. "tariffs" → sell manufacturing tickers)
- [ ] **ANLYS-03**: System discards signals below confidence threshold (default 0.7) — logs them but never executes
- [ ] **ANLYS-04**: System stores full signal audit record per post: raw LLM prompt, raw LLM response, keyword matches, final action, and reason code

### Trading

- [ ] **TRADE-01**: User can run the bot in paper trading mode (Alpaca paper environment — simulated money, real prices) as the default mode
- [ ] **TRADE-02**: User can switch to live trading mode via Alpaca after paper pipeline is validated (explicit two-step confirmation required)
- [ ] **TRADE-03**: System places all entry orders as Alpaca bracket orders (atomic entry + stop-loss) — never two separate submissions
- [ ] **TRADE-04**: System checks market hours before executing any order and discards signals that are stale (older than configurable threshold) to prevent acting on overnight posts at open

### Risk

- [ ] **RISK-01**: User can set position size as % of portfolio (maps to low/medium/high risk level) and system respects it per trade
- [ ] **RISK-02**: User can set stop-loss threshold % and system attaches it as bracket stop calculated from actual fill price
- [ ] **RISK-03**: System enforces max daily loss cap by reading live Alpaca account value before each trade and halting all trading when cap is reached

### Dashboard

- [ ] **DASH-01**: User can view a live post feed showing incoming Trump posts with their LLM analysis result overlaid (WebSocket push)
- [ ] **DASH-02**: User can view a full trade log showing the chain: post → signal → order → fill with all audit fields
- [ ] **DASH-03**: User can view current portfolio positions and P&L reading live from Alpaca API (not bot's internal state)
- [ ] **DASH-04**: User can toggle the bot on/off from the dashboard with a kill switch; dashboard shows an error/alert panel for scraper failures and API errors

### Comparison

- [ ] **COMP-01**: System maintains a SPY shadow portfolio (pure NAV math, no Alpaca orders) over the same active period for benchmark comparison
- [ ] **COMP-02**: System maintains a QQQ shadow portfolio (pure NAV math) over the same active period for benchmark comparison
- [ ] **COMP-03**: System maintains a random-trade baseline shadow portfolio (random buy/sell of watchlist tickers) over the same active period
- [ ] **COMP-04**: User can view a comparison chart showing bot performance vs. SPY, QQQ, and random baseline on the dashboard

### Settings

- [ ] **SETT-01**: User can add and remove stock tickers from the watchlist; bot only ever trades tickers on the watchlist
- [ ] **SETT-02**: User can set risk controls from the dashboard: position size %, stop-loss %, and max daily loss cap

## v2 Requirements

### Settings (UI)

- **SETT-03**: User can add and edit keyword → action rules from the dashboard UI
- **SETT-04**: User can adjust the confidence threshold (default 0.7) from the dashboard UI

### Congress Tracking

- **CONG-01**: System monitors Congress member trade disclosures and generates signals based on their reported trades
- **CONG-02**: User can view Congress member trades alongside Trump signal performance for comparison

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-user support / authentication | Personal single-user tool — adds complexity with no benefit |
| Mobile app | Web dashboard accessible on phone via browser is sufficient |
| Backtesting on historical data | Complex to implement correctly; core value is live signal execution |
| Options / derivatives trading | Alpaca supports it but adds significant risk management complexity |
| Real-time WebSocket tweet streaming | Polling at 1-5 min intervals is sufficient for this use case |
| Custom comparison strategies | SPY/QQQ/random covers the meaningful benchmarks |
| Notifications (email/SMS) | Dashboard monitoring is sufficient for personal use |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INGEST-01 | Phase 3 | Pending |
| INGEST-02 | Phase 3 | Pending |
| INGEST-03 | Phase 3 | Pending |
| INGEST-04 | Phase 3 | Pending |
| ANLYS-01 | Phase 4 | Pending |
| ANLYS-02 | Phase 4 | Pending |
| ANLYS-03 | Phase 4 | Pending |
| ANLYS-04 | Phase 4 | Pending |
| TRADE-01 | Phase 2 | Pending |
| TRADE-02 | Phase 7 | Pending |
| TRADE-03 | Phase 2 | Pending |
| TRADE-04 | Phase 5 | Pending |
| RISK-01 | Phase 5 | Pending |
| RISK-02 | Phase 5 | Pending |
| RISK-03 | Phase 5 | Pending |
| DASH-01 | Phase 6 | Pending |
| DASH-02 | Phase 6 | Pending |
| DASH-03 | Phase 6 | Pending |
| DASH-04 | Phase 6 | Pending |
| COMP-01 | Phase 7 | Pending |
| COMP-02 | Phase 7 | Pending |
| COMP-03 | Phase 7 | Pending |
| COMP-04 | Phase 7 | Pending |
| SETT-01 | Phase 1 | Pending |
| SETT-02 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 25 total
- Mapped to phases: 25
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-19*
*Last updated: 2026-04-19 after initial definition*
