import { useQuery } from "@tanstack/react-query"
import { Skeleton } from "@/components/ui/skeleton"
import { Card, CardContent } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"
import type { PortfolioData } from "@/lib/api"

function formatCurrency(n: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n)
}

function PnlValue({ value }: { value: number }) {
  const color = value > 0 ? "text-green-400" : value < 0 ? "text-red-400" : "text-foreground"
  const prefix = value > 0 ? "+" : ""
  return (
    <span className={cn("text-3xl font-semibold", color)}>
      {prefix}{formatCurrency(value)}
    </span>
  )
}

function SummaryCards({ data }: { data: PortfolioData }) {
  return (
    <div className="grid grid-cols-3 gap-4 mb-6">
      <Card>
        <CardContent className="p-6">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Total Equity
          </p>
          <p className="text-3xl font-semibold text-foreground mt-2">
            {formatCurrency(data.equity)}
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-6">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            P&amp;L Today
          </p>
          <div className="mt-2">
            <PnlValue value={data.pl_today} />
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-6">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Buying Power
          </p>
          <p className="text-3xl font-semibold text-foreground mt-2">
            {formatCurrency(data.buying_power)}
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

function PositionsTable({ data }: { data: PortfolioData }) {
  if (data.positions.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-xl font-semibold mb-2">No open positions</p>
        <p className="text-sm text-muted-foreground">The bot has no active positions right now.</p>
      </div>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Symbol</TableHead>
          <TableHead>Qty</TableHead>
          <TableHead>Market Value</TableHead>
          <TableHead>Avg Entry</TableHead>
          <TableHead>Unrealized P&amp;L</TableHead>
          <TableHead>% Change</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.positions.map(pos => {
          const plColor = pos.unrealized_pl > 0
            ? "text-green-400"
            : pos.unrealized_pl < 0
            ? "text-red-400"
            : "text-foreground"
          const pct = (pos.unrealized_plpc * 100).toFixed(2)
          return (
            <TableRow key={pos.symbol}>
              <TableCell className="font-semibold">{pos.symbol}</TableCell>
              <TableCell className="tabular-nums">{pos.qty}</TableCell>
              <TableCell className="tabular-nums">{formatCurrency(pos.market_value)}</TableCell>
              <TableCell className="tabular-nums">{formatCurrency(pos.avg_entry_price)}</TableCell>
              <TableCell className={cn("tabular-nums font-semibold", plColor)}>
                {pos.unrealized_pl >= 0 ? "+" : ""}{formatCurrency(pos.unrealized_pl)}
              </TableCell>
              <TableCell className={cn("tabular-nums", plColor)}>
                {pos.unrealized_plpc >= 0 ? "+" : ""}{pct}%
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}

function LoadingSkeletons() {
  return (
    <div className="p-6 space-y-4">
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map(i => <Skeleton key={i} className="h-24 rounded-lg" />)}
      </div>
      {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-10 w-full rounded" />)}
    </div>
  )
}

export default function PortfolioPage() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["portfolio"],
    queryFn: () => api.portfolio(),
    staleTime: 10_000,
    refetchInterval: 15_000,   // live Alpaca data — poll every 15s (D-03)
  })

  if (isPending) return <LoadingSkeletons />

  if (isError) {
    return (
      <div className="p-6">
        <Alert variant="destructive">
          <AlertDescription>
            <strong>Portfolio unavailable.</strong>{" "}
            Unable to reach Alpaca API. Check your credentials and try again.
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold mb-6">Portfolio</h1>
      <SummaryCards data={data} />
      <PositionsTable data={data} />
    </div>
  )
}
