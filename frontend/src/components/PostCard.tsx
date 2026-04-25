import { Globe, X as XIcon } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

// Union type — PostCard accepts both REST PostItem and WS PostFeedMessage
export interface PostCardData {
  id: number
  platform: string
  content: string
  posted_at: string
  is_filtered: boolean
  filter_reason: string | null
  signal?: {
    sentiment: string
    confidence: number
    affected_tickers: string[]
    final_action?: string | null
    reason_code?: string | null
  } | null
  isNew?: boolean  // true for WebSocket-inserted cards — triggers slide-in animation
}

// Relative timestamp using Intl.RelativeTimeFormat (no date-fns dep needed)
function relativeTime(isoString: string): string {
  const now = Date.now()
  const then = new Date(isoString).getTime()
  const diffSeconds = Math.round((now - then) / 1000)

  if (diffSeconds < 60) return `${diffSeconds}s ago`
  const diffMinutes = Math.round(diffSeconds / 60)
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  const diffHours = Math.round(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.round(diffHours / 24)
  return `${diffDays}d ago`
}

function SentimentBadge({ sentiment }: { sentiment: string; confidence: number }) {
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

function PlatformIcon({ platform }: { platform: string }) {
  if (platform === "twitter") return <XIcon size={16} className="text-muted-foreground" />
  return <Globe size={16} className="text-muted-foreground" />
}

export default function PostCard({ post }: { post: PostCardData }) {
  const isFiltered = post.is_filtered

  return (
    <Card
      className={cn(
        "mb-2 transition-all",
        isFiltered && "opacity-40",
        post.isNew && "animate-in slide-in-from-top-2 fade-in duration-200"
      )}
    >
      <CardContent className="p-4">
        {/* Header row — platform icon + timestamp */}
        <div className="flex items-center gap-2 mb-2">
          <PlatformIcon platform={post.platform} />
          <span className="text-xs text-muted-foreground">{relativeTime(post.posted_at)}</span>
        </div>

        {/* Post text */}
        <p className="text-sm leading-relaxed text-foreground mb-3">{post.content}</p>

        {/* Footer row — sentiment badge + tickers OR filtered label */}
        {isFiltered ? (
          <div>
            <span className="text-xs font-semibold text-muted-foreground">Filtered</span>
            {post.filter_reason && (
              <p className="text-xs text-muted-foreground italic mt-0.5">
                {post.filter_reason}
              </p>
            )}
          </div>
        ) : post.signal ? (
          <div className="flex items-center flex-wrap gap-2">
            <SentimentBadge
              sentiment={post.signal.sentiment}
              confidence={post.signal.confidence}
            />
            <span className="text-xs text-muted-foreground">
              {Math.round(post.signal.confidence * 100)}%
            </span>
            {post.signal.affected_tickers.map(ticker => (
              <Badge key={ticker} variant="outline" className="text-xs">
                {ticker}
              </Badge>
            ))}
          </div>
        ) : (
          <span className="text-xs text-muted-foreground italic">Analysing…</span>
        )}
      </CardContent>
    </Card>
  )
}
