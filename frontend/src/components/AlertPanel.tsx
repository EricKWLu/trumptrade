import { useQuery } from "@tanstack/react-query"
import { AlertTriangle, XCircle } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { api } from "@/lib/api"
import type { AlertItem } from "@/lib/api"

function AlertIcon({ source }: { source: string }) {
  // LLM failures and Alpaca errors = XCircle (error); scraper silence = AlertTriangle (warning)
  if (source.includes("alpaca") || source.includes("llm")) {
    return <XCircle size={14} className="text-destructive shrink-0" />
  }
  return <AlertTriangle size={14} className="text-yellow-400 shrink-0" />
}

export default function AlertPanel() {
  const { data: alerts = [] } = useQuery({
    queryKey: ["alerts"],
    queryFn: () => api.alerts(),
    refetchInterval: 10_000,  // poll every 10s (D-10)
    staleTime: 0,
  })

  if (alerts.length === 0) return null

  return (
    <div className="px-2 py-2">
      <div className="flex items-center gap-2 px-1 mb-2">
        <span className="text-xs text-muted-foreground font-semibold uppercase tracking-wide">Alerts</span>
        <Badge className="bg-destructive text-destructive-foreground text-xs px-1.5 py-0.5 rounded-full">
          {alerts.length}
        </Badge>
      </div>
      <ScrollArea className="max-h-60">
        <div className="space-y-1">
          {alerts.map((alert: AlertItem, i: number) => (
            <Alert key={i} className="py-2 px-3">
              <div className="flex items-start gap-2">
                <AlertIcon source={alert.source} />
                <div className="flex-1 min-w-0">
                  <AlertDescription className="text-xs leading-snug line-clamp-2">
                    {alert.message}
                  </AlertDescription>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {alert.source} · {new Date(alert.ts).toLocaleTimeString()}
                  </p>
                </div>
              </div>
            </Alert>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
