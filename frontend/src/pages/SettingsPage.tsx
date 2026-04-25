import { useState, useEffect } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { LiveModeModal } from "@/components/LiveModeModal"
import { X, Plus } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"
import type { RiskSettings } from "@/lib/api"

// ── Watchlist Section ─────────────────────────────────────────────────────────

function WatchlistSection() {
  const queryClient = useQueryClient()
  const [newTicker, setNewTicker] = useState("")
  const [addError, setAddError] = useState<string | null>(null)

  const { data: watchlist = [], isPending } = useQuery({
    queryKey: ["watchlist"],
    queryFn: () => api.watchlist(),
    staleTime: 60_000,
  })

  const addMutation = useMutation({
    mutationFn: (symbol: string) => api.addWatchlist(symbol),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watchlist"] })
      setNewTicker("")
      setAddError(null)
    },
    onError: (err: Error) => {
      if (err.message.startsWith("409")) {
        setAddError("This ticker is already on your watchlist.")
      } else {
        setAddError("Failed to add ticker. Try again.")
      }
    },
  })

  const removeMutation = useMutation({
    mutationFn: (symbol: string) => api.removeWatchlist(symbol),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watchlist"] })
    },
  })

  function handleAdd() {
    const symbol = newTicker.trim().toUpperCase()
    if (!symbol) { setAddError("Enter a ticker symbol."); return }
    if (!/^[A-Z]{1,5}$/.test(symbol)) { setAddError("Ticker must be 1–5 letters only."); return }
    setAddError(null)
    addMutation.mutate(symbol)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl font-semibold">Watchlist</CardTitle>
        <p className="text-sm text-muted-foreground">
          Add or remove tickers. The bot only trades symbols on this list.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {isPending ? (
          <div className="flex flex-wrap gap-2">
            {[1, 2, 3].map(i => <Skeleton key={i} className="h-7 w-16 rounded-full" />)}
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {watchlist.map(({ symbol }) => (
              <Badge
                key={symbol}
                variant="outline"
                className="flex items-center gap-1 px-2 py-1 text-xs font-semibold"
              >
                {symbol}
                <button
                  className={cn("ml-1 text-muted-foreground hover:text-destructive transition-colors")}
                  onClick={() => removeMutation.mutate(symbol)}
                  disabled={removeMutation.status === "pending"}
                  aria-label={`Remove ${symbol}`}
                >
                  <X size={12} />
                </button>
              </Badge>
            ))}
            {watchlist.length === 0 && (
              <p className="text-sm text-muted-foreground">No tickers yet. Add one below.</p>
            )}
          </div>
        )}

        {/* Add ticker input row */}
        <div className="flex gap-2">
          <div className="flex-1">
            <Input
              placeholder="Add ticker, e.g. AAPL"
              value={newTicker}
              onChange={e => { setNewTicker(e.target.value.toUpperCase()); setAddError(null) }}
              onKeyDown={e => e.key === "Enter" && handleAdd()}
              maxLength={5}
              className="uppercase"
            />
            {addError && (
              <p className="text-xs text-destructive mt-1">{addError}</p>
            )}
          </div>
          <Button
            onClick={handleAdd}
            disabled={addMutation.status === "pending"}
            size="default"
          >
            <Plus size={14} className="mr-2" />
            Add Ticker
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Risk Controls Section ─────────────────────────────────────────────────────

function RiskControlsSection() {
  const queryClient = useQueryClient()
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle")

  // Local form state — 4 controlled inputs
  const [form, setForm] = useState<RiskSettings>({
    max_position_size_pct: 2.0,
    stop_loss_pct: 5.0,
    max_daily_loss_dollars: 500,
    signal_staleness_minutes: 5,
  })

  const { data: riskSettings } = useQuery({
    queryKey: ["settings", "risk"],
    queryFn: () => api.riskSettings(),
    staleTime: 60_000,
  })

  // Populate form when data loads
  useEffect(() => {
    if (riskSettings) setForm(riskSettings)
  }, [riskSettings])

  const saveMutation = useMutation({
    mutationFn: (data: RiskSettings) => api.patchRiskSettings(data),
    onMutate: () => setSaveStatus("saving"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "risk"] })
      setSaveStatus("saved")
      setTimeout(() => setSaveStatus("idle"), 3000)  // fade after 3s
    },
    onError: () => setSaveStatus("error"),
  })

  function handleChange(field: keyof RiskSettings, value: string) {
    const parsed = parseFloat(value)
    if (!isNaN(parsed)) {
      setForm(prev => ({ ...prev, [field]: parsed }))
    }
  }

  const FIELDS: Array<{
    key: keyof RiskSettings
    label: string
    placeholder: string
    hint: string
  }> = [
    { key: "max_position_size_pct", label: "Max Position Size", placeholder: "2.0", hint: "% of portfolio" },
    { key: "stop_loss_pct", label: "Stop-Loss", placeholder: "5.0", hint: "% from fill price" },
    { key: "max_daily_loss_dollars", label: "Max Daily Loss", placeholder: "500", hint: "dollars" },
    { key: "signal_staleness_minutes", label: "Signal Staleness", placeholder: "5", hint: "minutes" },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl font-semibold">Risk Controls</CardTitle>
        <p className="text-sm text-muted-foreground">Changes take effect on the next signal.</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          {FIELDS.map(({ key, label, placeholder, hint }) => (
            <div key={key} className="space-y-1">
              <label className="text-sm font-semibold text-foreground">{label}</label>
              <Input
                type="number"
                placeholder={placeholder}
                value={form[key]}
                onChange={e => handleChange(key, e.target.value)}
                step={key.includes("minutes") ? "1" : "0.1"}
                min="0"
              />
              <p className="text-xs text-muted-foreground">{hint}</p>
            </div>
          ))}
        </div>

        <div className="flex items-center gap-3 pt-2">
          <Button
            onClick={() => saveMutation.mutate(form)}
            disabled={saveStatus === "saving"}
            className="w-full"
          >
            {saveStatus === "saving" ? "Saving…" : "Save Changes"}
          </Button>
        </div>

        {saveStatus === "saved" && (
          <p className="text-sm text-green-400">Settings saved.</p>
        )}
        {saveStatus === "error" && (
          <p className="text-sm text-destructive">Failed to save. Try again.</p>
        )}
      </CardContent>
    </Card>
  )
}

// ── Trading Mode Section ──────────────────────────────────────────────────────

function TradingModeSection() {
  const [modalOpen, setModalOpen] = useState(false)
  const { data: modeData } = useQuery({
    queryKey: ["trading-mode"],
    queryFn: () => api.tradingMode(),
    staleTime: 0,
  })
  const mode = modeData?.trading_mode ?? "paper"

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl font-semibold">Trading Mode</CardTitle>
        <p className="text-sm text-muted-foreground">
          Switch between paper (simulated) and live (real money) trading.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-foreground">Current mode:</span>
          {mode === "live" ? (
            <Badge className="bg-red-500/10 text-red-400 border border-red-500/20 font-semibold text-xs">
              LIVE
            </Badge>
          ) : (
            <Badge className="bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 font-semibold text-xs">
              PAPER
            </Badge>
          )}
        </div>
        <Button
          variant={mode === "live" ? "outline" : "destructive"}
          onClick={() => setModalOpen(true)}
        >
          {mode === "live" ? "Switch to PAPER Trading" : "Switch to LIVE Trading"}
        </Button>
        <LiveModeModal
          isLive={mode === "live"}
          open={modalOpen}
          onClose={() => setModalOpen(false)}
        />
      </CardContent>
    </Card>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-xl font-semibold mb-6">Settings</h1>
      <div className="space-y-8">
        <WatchlistSection />
        <RiskControlsSection />
        <TradingModeSection />
      </div>
    </div>
  )
}
