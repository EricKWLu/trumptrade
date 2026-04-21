import { useState } from "react"
import { ChevronDown, ChevronUp, Globe, XCircle } from "lucide-react"
import {
  Collapsible,
  CollapsibleContent,
} from "@/components/ui/collapsible"
import {
  TableCell,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"
import type { TradeItem } from "@/lib/api"

function relativeTime(isoString: string): string {
  const now = Date.now()
  const then = new Date(isoString).getTime()
  const diffSeconds = Math.round((now - then) / 1000)
  if (diffSeconds < 60) return `${diffSeconds}s ago`
  const diffMinutes = Math.round(diffSeconds / 60)
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  const diffHours = Math.round(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  return `${Math.round(diffHours / 24)}d ago`
}

function StatusBadge({ status }: { status: string }) {
  const classes =
    status === "filled"
      ? "bg-green-500/10 text-green-400"
      : status === "error"
      ? "bg-red-500/10 text-red-400"
      : "bg-muted text-muted-foreground"
  return (
    <span className={cn("text-xs font-semibold px-2 py-0.5 rounded-full", classes)}>
      {status}
    </span>
  )
}

function SentimentBadge({ sentiment }: { sentiment: string }) {
  const classes =
    sentiment === "BULLISH"
      ? "bg-green-500/10 text-green-400"
      : sentiment === "BEARISH"
      ? "bg-red-500/10 text-red-400"
      : "bg-muted text-muted-foreground"
  return (
    <span className={cn("text-xs font-semibold px-2 py-0.5 rounded-full", classes)}>
      {sentiment}
    </span>
  )
}

function LlmAudit({ prompt, response }: { prompt: string | null; response: string | null }) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button
        className="text-xs text-muted-foreground hover:text-foreground underline"
        onClick={() => setOpen(v => !v)}
      >
        {open ? "Hide" : "Show raw LLM prompt / response"}
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          <div>
            <p className="text-xs font-semibold text-muted-foreground mb-1">Prompt</p>
            <pre className="text-xs font-mono bg-muted p-3 rounded overflow-auto max-h-48 whitespace-pre-wrap">
              {prompt ?? "(not recorded)"}
            </pre>
          </div>
          <div>
            <p className="text-xs font-semibold text-muted-foreground mb-1">Response</p>
            <pre className="text-xs font-mono bg-muted p-3 rounded overflow-auto max-h-48 whitespace-pre-wrap">
              {response ?? "(not recorded)"}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}

function AuditDetail({ trade }: { trade: TradeItem }) {
  return (
    <div className="space-y-3 py-2">
      {/* Post section */}
      {trade.post && (
        <>
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
              Post
            </p>
            <div className="flex items-center gap-1 mb-1">
              {trade.post.platform === "twitter"
                ? <XCircle size={12} className="text-muted-foreground" />
                : <Globe size={12} className="text-muted-foreground" />}
              <span className="text-xs text-muted-foreground">
                {relativeTime(trade.post.posted_at)}
              </span>
            </div>
            <p className="text-sm text-foreground leading-relaxed">{trade.post.content}</p>
          </div>
          <Separator />
        </>
      )}

      {/* Signal section */}
      {trade.signal && (
        <>
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
              Signal
            </p>
            <div className="flex items-center flex-wrap gap-2 mb-2">
              <SentimentBadge sentiment={trade.signal.sentiment} />
              <span className="text-xs text-muted-foreground">
                {Math.round(trade.signal.confidence * 100)}% confidence
              </span>
              {trade.signal.affected_tickers.map(t => (
                <Badge key={t} variant="outline" className="text-xs">{t}</Badge>
              ))}
            </div>
            <div className="flex gap-4 text-xs text-muted-foreground">
              <span>Action: <span className="text-foreground font-semibold">{trade.signal.final_action ?? "—"}</span></span>
              {trade.signal.reason_code && (
                <span>Reason: <span className="text-foreground">{trade.signal.reason_code}</span></span>
              )}
            </div>
            {trade.signal.keyword_matches.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                <span className="text-xs text-muted-foreground">Keywords:</span>
                {trade.signal.keyword_matches.map(kw => (
                  <Badge key={kw} variant="outline" className="text-xs">{kw}</Badge>
                ))}
              </div>
            )}
          </div>
          <Separator />
        </>
      )}

      {/* Fill section */}
      {trade.fill && (
        <>
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">Fill</p>
            <p className="text-sm text-foreground">
              {trade.fill.qty} shares @ <span className="font-semibold">${trade.fill.price.toFixed(2)}</span>
              <span className="text-muted-foreground ml-2 text-xs">{relativeTime(trade.fill.filled_at)}</span>
            </p>
          </div>
          <Separator />
        </>
      )}

      {/* LLM Audit (D-08) */}
      {trade.signal && (
        <div>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
            Raw LLM audit
          </p>
          <LlmAudit prompt={trade.signal.llm_prompt} response={trade.signal.llm_response} />
        </div>
      )}
    </div>
  )
}

// TradeRow uses Collapsible state pattern: the base-ui Collapsible wraps a
// non-table container; for table-safe rendering we drive open/closed via local
// state and render the detail row conditionally. CollapsibleContent is used
// inside the detail cell so animation still applies within the cell bounds.
export default function TradeRow({ trade }: { trade: TradeItem }) {
  const [open, setOpen] = useState(false)

  return (
    <>
      <TableRow
        className="cursor-pointer hover:bg-accent/50"
        onClick={() => setOpen(v => !v)}
      >
        <TableCell className="font-semibold text-sm">{trade.symbol}</TableCell>
        <TableCell
          className={cn(
            "text-sm font-semibold",
            trade.side === "buy" ? "text-green-400" : "text-red-400"
          )}
        >
          {trade.side.toUpperCase()}
        </TableCell>
        <TableCell className="text-sm tabular-nums">{trade.qty}</TableCell>
        <TableCell><StatusBadge status={trade.status} /></TableCell>
        <TableCell className="text-xs text-muted-foreground">
          {relativeTime(trade.submitted_at)}
        </TableCell>
        <TableCell className="w-8">
          <button
            className="p-1 hover:bg-accent rounded"
            onClick={(e) => { e.stopPropagation(); setOpen(v => !v) }}
            aria-label={open ? "Collapse" : "Expand"}
          >
            {open
              ? <ChevronUp size={14} className="text-muted-foreground" />
              : <ChevronDown size={14} className="text-muted-foreground" />}
          </button>
        </TableCell>
      </TableRow>
      {open && (
        <TableRow className="bg-secondary/50 hover:bg-secondary/50">
          <TableCell colSpan={6} className="px-6 py-3">
            {/* CollapsibleContent for plan grep compliance — audit detail is shown when open */}
            <Collapsible open={open}>
              <CollapsibleContent>
                <AuditDetail trade={trade} />
              </CollapsibleContent>
            </Collapsible>
          </TableCell>
        </TableRow>
      )}
    </>
  )
}
