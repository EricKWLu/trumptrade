import { NavLink, Outlet } from "react-router-dom"
import { Zap, BarChart2, TrendingUp, Settings, LineChart } from "lucide-react"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import KillSwitchBtn from "./KillSwitchBtn"
import AlertPanel from "./AlertPanel"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"

const NAV_ITEMS = [
  { to: "/", end: true, icon: Zap, label: "Feed" },
  { to: "/trades", end: false, icon: BarChart2, label: "Trades" },
  { to: "/portfolio", end: false, icon: TrendingUp, label: "Portfolio" },
  { to: "/benchmarks", end: false, icon: LineChart, label: "Benchmarks" },
  { to: "/settings", end: false, icon: Settings, label: "Settings" },
]

function TradingModeBadge() {
  const { data } = useQuery({
    queryKey: ["portfolio-mode"],
    queryFn: () => api.portfolio(),
    staleTime: 30_000,
    refetchInterval: 60_000,
  })
  const mode = data?.trading_mode ?? "paper"
  if (mode === "live") {
    return (
      <div className="px-3 py-2">
        <Badge className="w-full justify-center bg-red-500/10 text-red-400 border border-red-500/20 font-semibold text-xs">
          LIVE
        </Badge>
      </div>
    )
  }
  return (
    <div className="px-3 py-2">
      <Badge className="w-full justify-center bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 font-semibold text-xs">
        PAPER
      </Badge>
    </div>
  )
}

export default function AppShell() {
  const { data: modeData } = useQuery({
    queryKey: ["portfolio-mode"],
    queryFn: () => api.portfolio(),
    staleTime: 30_000,
    refetchInterval: 60_000,
  })
  const mode = modeData?.trading_mode ?? "paper"

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar — 240px fixed, never collapses (D-01) */}
      <aside className="w-60 flex-shrink-0 flex flex-col bg-sidebar border-r border-border">
        {/* Kill switch — always at top of sidebar (D-09) */}
        <div className="px-3 pt-3 pb-2">
          <KillSwitchBtn />
        </div>

        <Separator />

        {/* Nav items — Feed, Trades, Portfolio, Settings */}
        <nav className="flex-1 px-2 py-3 space-y-1">
          {NAV_ITEMS.map(({ to, end, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground border-l-2 border-primary"
                    : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground"
                )
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        <Separator />

        {/* Alert panel — below nav (D-10) */}
        <AlertPanel />

        {/* PAPER/LIVE badge — bottom of sidebar (D-02) */}
        <TradingModeBadge />
      </aside>

      {/* Main content area */}
      <main className="flex-1 overflow-auto">
        {mode === "live" && (
          <div className="bg-red-500/10 border-b border-red-500/30 px-4 py-2 text-center text-red-400 text-sm font-semibold tracking-wide">
            LIVE TRADING ACTIVE — real money at risk
          </div>
        )}
        <Outlet />
      </main>
    </div>
  )
}
