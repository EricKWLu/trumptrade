# Phase 4: LLM Analysis Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-21
**Phase:** 04-llm-analysis-engine
**Areas discussed:** LLM provider & model

---

## LLM Provider & Model

| Option | Description | Selected |
|--------|-------------|----------|
| Anthropic (Claude) | claude-haiku-4-5, tool_use structured output | ✓ (default) |
| OpenAI (GPT) | gpt-4o-mini, JSON mode | |
| Groq (free) | llama-3.3-70b-versatile, free tier | ✓ (adapter built) |
| Gemini Flash (free) | gemini-2.0-flash, free tier | |

**User's input:** Wants to avoid subscription lock-in — needs easy switching between providers. Interested in free options. Groq recommended as free fallback.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Config-driven via app_settings | llm_provider + llm_model DB keys, runtime switch | ✓ |
| Environment variable (.env) | Requires server restart to switch | |

**User's choice:** Config-driven via app_settings

---

| Option | Description | Selected |
|--------|-------------|----------|
| Anthropic (paid, default) | Best structured output, ~$0.001/post | ✓ |
| Groq (free fallback) | Free tier, fast, llama-3.3-70b | ✓ |
| OpenAI (paid) | Not selected |  |
| Gemini (free) | Not selected | |

**User's choice:** Build adapters for Anthropic + Groq. Default: Anthropic.

---

## Claude's Discretion

Analysis trigger (30s APScheduler polling), keyword rule conflict resolution (highest priority
wins), prompt design (static system prompt + dynamic watchlist injection), Pydantic validation
stripping non-watchlist tickers — all applied from ANLYS-01/02/03/04 requirements and
established codebase patterns.

## Deferred Ideas

None.
