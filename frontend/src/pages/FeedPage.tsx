import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { Zap } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { ScrollArea } from "@/components/ui/scroll-area"
import { usePostFeed } from "@/hooks/usePostFeed"
import PostCard, { type PostCardData } from "@/components/PostCard"
import { api, type PostItem } from "@/lib/api"
import { cn } from "@/lib/utils"

function LoadingSkeletons() {
  return (
    <div className="space-y-2 p-6">
      {[1, 2, 3, 4].map(i => (
        <Skeleton key={i} className="h-24 w-full rounded-lg" />
      ))}
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-12">
      <Zap size={48} className="text-muted-foreground mb-4" />
      <h2 className="text-xl font-semibold mb-2">No posts yet</h2>
      <p className="text-sm text-muted-foreground">
        Waiting for Trump to post. The feed will update automatically.
      </p>
    </div>
  )
}

// Convert REST PostItem to PostCardData (no signal field available from REST)
function restToCard(p: PostItem): PostCardData {
  return {
    id: p.id,
    platform: p.platform,
    content: p.content,
    posted_at: p.posted_at,
    is_filtered: p.is_filtered,
    filter_reason: p.filter_reason,
    signal: null,
    isNew: false,
  }
}

export default function FeedPage() {
  // Initial load from REST — newest-first, 50 posts
  const { data: restPosts, isPending, isError } = useQuery({
    queryKey: ["posts"],
    queryFn: () => api.posts(50, 0),
    staleTime: 30_000,
  })

  // Live WebSocket feed — new posts prepended as they arrive
  const { posts: livePosts, status } = usePostFeed()

  // Merge: live posts (newest) at top, then REST posts that aren't already live
  // De-duplicate by id — live posts always win (they have signal data)
  const allPosts = useMemo<PostCardData[]>(() => {
    const liveIds = new Set(livePosts.map(p => p.id))
    const liveCards: PostCardData[] = livePosts.map(p => ({
      id: p.id,
      platform: p.platform,
      content: p.content,
      posted_at: p.posted_at,
      is_filtered: p.is_filtered,
      filter_reason: p.filter_reason,
      signal: p.signal,
      isNew: true,
    }))
    const restCards: PostCardData[] = (restPosts ?? [])
      .filter(p => !liveIds.has(p.id))
      .map(restToCard)
    return [...liveCards, ...restCards]
  }, [livePosts, restPosts])

  if (isPending) return <LoadingSkeletons />

  if (isError) {
    return (
      <div className="p-6">
        <p className="text-sm text-destructive">Failed to load posts. Is the backend running?</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border">
        <h1 className="text-xl font-semibold">Feed</h1>
        {/* WebSocket status chip (D-06 reconnect behavior) */}
        {status !== "connected" && (
          <span
            className={cn(
              "text-xs px-2 py-1 rounded-full font-semibold",
              status === "reconnecting"
                ? "bg-yellow-500/10 text-yellow-400"
                : "bg-muted text-muted-foreground"
            )}
          >
            {status === "reconnecting" ? "Reconnecting to live feed…" : "Disconnected"}
          </span>
        )}
      </div>

      {/* Post list */}
      <ScrollArea className="flex-1">
        <div className="p-6">
          {allPosts.length === 0 ? (
            <EmptyState />
          ) : (
            allPosts.map(post => <PostCard key={post.id} post={post} />)
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
