// Typed fetch wrappers for all backend endpoints.
// BASE = "" — same-origin in prod; Vite CORS header handles dev.

const BASE = ""

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

// ── Types ──────────────────────────────────────────────────────────────────

export interface PostItem {
  id: number
  platform: string              // "truth_social" | "twitter"
  content: string
  posted_at: string             // ISO 8601
  created_at: string
  is_filtered: boolean
  filter_reason: string | null
  signal: {
    sentiment: string
    confidence: number
    affected_tickers: string[]
    final_action: string | null
    reason_code: string | null
  } | null
}

export interface SignalDetail {
  id: number
  sentiment: string             // "BULLISH" | "BEARISH" | "NEUTRAL"
  confidence: number
  affected_tickers: string[]
  final_action: string | null
  reason_code: string | null
  keyword_matches: string[]
  llm_prompt: string | null
  llm_response: string | null
}

export interface FillDetail {
  id: number
  qty: number
  price: number
  filled_at: string
}

export interface TradeItem {
  id: number
  symbol: string
  side: string                  // "buy" | "sell"
  qty: number
  status: string
  order_type: string
  submitted_at: string
  filled_at: string | null
  fill_price: number | null
  trading_mode: string
  alpaca_order_id: string
  signal: SignalDetail | null
  post: PostItem | null
  fill: FillDetail | null
}

export interface PositionItem {
  symbol: string
  qty: number
  market_value: number
  avg_entry_price: number
  unrealized_pl: number
  unrealized_plpc: number
}

export interface PortfolioData {
  equity: number
  last_equity: number
  pl_today: number
  buying_power: number
  trading_mode: string
  positions: PositionItem[]
}

export interface WatchlistItem {
  symbol: string
  added_at: string
}

export interface RiskSettings {
  max_position_size_pct: number
  stop_loss_pct: number
  max_daily_loss_dollars: number
  signal_staleness_minutes: number
}

export interface AlertItem {
  source: string
  message: string
  ts: string
}

export interface BenchmarkPoint {
  date: string          // "YYYY-MM-DD"
  bot: number | null    // % return from start, null if not yet started
  spy: number | null
  qqq: number | null
  random: number | null
}

export interface SetModeResponse {
  trading_mode: string
  ok: boolean
}

export interface PostFeedMessage {
  type: "post"
  id: number
  platform: string
  content: string
  posted_at: string
  is_filtered: boolean
  filter_reason: string | null
  signal: {
    sentiment: string
    confidence: number
    affected_tickers: string[]
    final_action: string
    reason_code: string | null
  } | null
}

// ── API client ──────────────────────────────────────────────────────────────

export const api = {
  posts: (limit = 50, offset = 0) =>
    apiFetch<PostItem[]>(`/posts?limit=${limit}&offset=${offset}`),

  trades: () =>
    apiFetch<TradeItem[]>("/trades"),

  portfolio: () =>
    apiFetch<PortfolioData>("/portfolio"),

  watchlist: () =>
    apiFetch<WatchlistItem[]>("/watchlist"),

  riskSettings: () =>
    apiFetch<RiskSettings>("/settings/risk"),

  alerts: () =>
    apiFetch<AlertItem[]>("/alerts"),

  addWatchlist: (symbol: string) =>
    apiFetch<{ symbol: string; added: boolean }>("/watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol }),
    }),

  removeWatchlist: (symbol: string) =>
    apiFetch<{ symbol: string; removed: boolean }>(`/watchlist/${symbol}`, {
      method: "DELETE",
    }),

  patchRiskSettings: (data: Partial<RiskSettings>) =>
    apiFetch<RiskSettings>("/settings/risk", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  toggleKillSwitch: (enabled: boolean) =>
    apiFetch<{ bot_enabled: boolean; ok: boolean }>("/trading/kill-switch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    }),

  benchmarks: () =>
    apiFetch<{ snapshots: BenchmarkPoint[] }>("/benchmarks").then((r) => r.snapshots),

  tradingMode: () =>
    apiFetch<{ trading_mode: string }>("/trading/mode"),

  setMode: (mode: "paper" | "live") =>
    apiFetch<SetModeResponse>("/trading/set-mode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode, confirmed: true }),
    }),
}
