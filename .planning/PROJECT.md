# TrumpTrade

## What This Is

A personal automated trading bot that monitors Donald Trump's posts on Truth Social and X/Twitter, analyzes them using AI sentiment analysis combined with keyword rules, and executes trades on a user-defined stock watchlist via the Alpaca brokerage API. Built for a single user with a web dashboard for monitoring and control.

## Core Value

Automatically detect and act on Trump's social media posts faster than a human can react — turning his words into trade signals before the market moves.

## Requirements

### Validated

- [x] User-defined stock watchlist (which tickers to trade) — **Validated in Phase 1: Foundation** (`watchlist` table with unique `symbol` column, Alembic migration verified)

### Active

- [ ] Monitor Trump's Truth Social profile for new posts (scraping, no official API)
- [ ] Monitor Trump's X/Twitter account for new posts (X API)
- [ ] Deduplicate posts across platforms (same content posted on both)
- [ ] Analyze posts via LLM sentiment analysis (bullish/bearish signal + confidence)
- [ ] Keyword rule layer as overlay/override on AI analysis
- [ ] User-defined stock watchlist (which tickers to trade)
- [ ] Risk settings: position size %, stop-loss threshold, max daily loss cap
- [ ] Test/paper trading mode using Alpaca paper environment (simulated money, real prices)
- [ ] Live trading mode via Alpaca API (real money)
- [ ] Web dashboard: live tweet feed with analysis, portfolio view, trade log, settings
- [ ] Comparison mode: shadow portfolios tracking SPY, QQQ, and random baseline over same period
- [ ] Trade execution with stop-loss orders attached automatically

### Out of Scope

- Congress member trade tracking — planned for later milestone
- Multi-user support / authentication — personal tool only
- Mobile app — web dashboard is sufficient
- Custom user-defined comparison strategies — three fixed benchmarks enough for v1
- Real-time WebSocket tweet streaming — polling is sufficient for v1

## Context

- Single-user personal tool, no authentication needed
- Python backend (trading logic, scraping, LLM calls, Alpaca SDK)
- Frontend: web dashboard (React or lightweight alternative)
- **Truth Social**: uses Mastodon-compatible JSON API (`/api/v1/accounts/:id/statuses`) via `httpx` polling — NOT HTML scraping
- **X/Twitter**: requires paid Basic developer tier (~$100/month) for API access; `tweepy` library
- **Alpaca**: paper trading is free; live trading requires a funded brokerage account
- Alpaca paper trading environment (`paper-api.alpaca.markets`) is the test mode backend
- Historical price data for comparison mode also available via Alpaca API
- The `alpaca-py` library handles all brokerage interactions (`from alpaca.trading.client import TradingClient`)

## Constraints

- **Data**: Truth Social has no public API — scraping is fragile and may break on site changes
- **Cost**: X/Twitter API access requires paid tier (~$100/month Basic)
- **Broker**: Alpaca account required; live trading needs funded account
- **LLM**: API costs per tweet analysis call (Claude or OpenAI)
- **Latency**: Not HFT — goal is "faster than a human", not millisecond execution

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| AI + keyword rules for analysis | AI for nuance, rules as override/fallback layer | — Pending |
| Fixed user watchlist (not dynamic sectors) | Simpler to reason about; user controls exposure | — Pending |
| Alpaca as broker | API-first, commission-free, has paper trading built-in | — Pending |
| Monitor both Truth Social + X | He posts on both; missing one means missed signals | — Pending |
| Python backend | Strong ecosystem for trading, scraping, and LLM integrations | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-19 after Phase 1: Foundation complete*
