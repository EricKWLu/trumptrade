import { useQuery } from "@tanstack/react-query"
import { BarChart2 } from "lucide-react"
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"
import { ScrollArea } from "@/components/ui/scroll-area"
import TradeRow from "@/components/TradeRow"
import { api } from "@/lib/api"

function LoadingSkeletons() {
  return (
    <div className="space-y-2 p-6">
      {[1, 2, 3, 4, 5, 6].map(i => (
        <Skeleton key={i} className="h-10 w-full rounded" />
      ))}
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-center p-12">
      <BarChart2 size={48} className="text-muted-foreground mb-4" />
      <h2 className="text-xl font-semibold mb-2">No trades yet</h2>
      <p className="text-sm text-muted-foreground">
        Trades will appear here once the bot places its first order.
      </p>
    </div>
  )
}

export default function TradesPage() {
  const { data: trades = [], isPending, isError } = useQuery({
    queryKey: ["trades"],
    queryFn: () => api.trades(),
    staleTime: 30_000,
  })

  if (isPending) return <LoadingSkeletons />

  if (isError) {
    return (
      <div className="p-6">
        <p className="text-sm text-destructive">Failed to load trades.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-4 border-b border-border">
        <h1 className="text-xl font-semibold">Trades</h1>
      </div>
      <ScrollArea className="flex-1">
        {trades.length === 0 ? (
          <EmptyState />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Symbol</TableHead>
                <TableHead>Side</TableHead>
                <TableHead>Qty</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Submitted</TableHead>
                <TableHead className="w-8" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {trades.map(trade => (
                <TradeRow key={trade.id} trade={trade} />
              ))}
            </TableBody>
          </Table>
        )}
      </ScrollArea>
    </div>
  )
}
