import { useQuery } from "@tanstack/react-query"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { api, type BenchmarkPoint } from "@/lib/api"

// ── BenchmarkChart ────────────────────────────────────────────────────────────
// Inline sub-component — no separate file needed (UI-SPEC Section 2d).
// All SVG styling uses inline style strings (Tailwind does not apply to SVG elements).

function BenchmarkChart({ data }: { data: BenchmarkPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={400}>
      <LineChart data={data} margin={{ top: 8, right: 24, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
          tickFormatter={(v: string) => v.slice(5)}
          minTickGap={40}
        />
        <YAxis
          tickFormatter={(v: number) => `${v.toFixed(1)}%`}
          tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
          label={{
            value: "Return since start (%)",
            angle: -90,
            position: "insideLeft",
            offset: 12,
            style: { fontSize: 12, fill: "hsl(var(--muted-foreground))" },
          }}
        />
        <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="4 4" />
        <Tooltip
          formatter={(value: number, name: string) => [`${value.toFixed(2)}%`, name.toUpperCase()]}
          labelFormatter={(label: string) => `Date: ${label}`}
          contentStyle={{
            background: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "0.5rem",
            fontSize: 12,
          }}
        />
        <Legend verticalAlign="bottom" wrapperStyle={{ paddingTop: 16, fontSize: 12 }} />
        <Line
          type="monotone"
          dataKey="bot"
          stroke="#3b82f6"
          dot={false}
          strokeWidth={2}
          name="Bot"
          connectNulls={false}
        />
        <Line
          type="monotone"
          dataKey="spy"
          stroke="#22c55e"
          dot={false}
          strokeWidth={2}
          name="SPY"
          connectNulls={false}
        />
        <Line
          type="monotone"
          dataKey="qqq"
          stroke="#a855f7"
          dot={false}
          strokeWidth={2}
          name="QQQ"
          connectNulls={false}
        />
        <Line
          type="monotone"
          dataKey="random"
          stroke="#f59e0b"
          dot={false}
          strokeWidth={2}
          name="Random"
          connectNulls={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

// ── Loading skeleton ──────────────────────────────────────────────────────────

function LoadingSkeletons() {
  return (
    <div className="p-6 space-y-4">
      <Skeleton className="h-6 w-48" />
      <Skeleton className="h-[400px] w-full rounded-lg" />
      <div className="flex justify-center gap-8 mt-4">
        {["Bot", "SPY", "QQQ", "Random"].map((s) => (
          <Skeleton key={s} className="h-4 w-16" />
        ))}
      </div>
    </div>
  )
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="text-center py-12">
      <p className="text-xl font-semibold mb-2">No benchmark data yet</p>
      <p className="text-sm text-muted-foreground">
        Check back after today&apos;s market close (4:01 PM ET).
        <br />
        The bot, SPY, QQQ, and random baseline all start together on the first snapshot.
      </p>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function BenchmarksPage() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["benchmarks"],
    queryFn: () => api.benchmarks(),
    staleTime: 300_000,       // 5 minutes — updates only at market close
    refetchInterval: 300_000,
  })

  if (isPending) return <LoadingSkeletons />

  if (isError) {
    return (
      <div className="p-6">
        <Alert variant="destructive">
          <AlertDescription>
            <strong>Benchmarks unavailable.</strong>{" "}
            Unable to load benchmark data. Check that the backend is running and try again.
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold mb-6">Benchmarks</h1>
      {!data || data.length === 0 ? (
        <EmptyState />
      ) : (
        <BenchmarkChart data={data} />
      )}
    </div>
  )
}
