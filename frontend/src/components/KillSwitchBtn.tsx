import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Square, Play, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { apiFetch } from "@/lib/api"

export default function KillSwitchBtn() {
  const queryClient = useQueryClient()

  // Fetch initial bot_enabled state from GET /trading/status (Plan 06-01 Step E).
  const { data: statusData } = useQuery({
    queryKey: ["trading-status"],
    queryFn: () => apiFetch<{ bot_enabled: boolean }>("/trading/status"),
    staleTime: Infinity,  // only needed once — mutations keep state in sync
  })

  // Local optimistic state seeded from server on first load.
  const [botEnabled, setBotEnabled] = useState<boolean | undefined>(undefined)
  // Sync server state into local state once on load
  if (statusData !== undefined && botEnabled === undefined) {
    setBotEnabled(statusData.bot_enabled)
  }
  const effectiveBotEnabled = botEnabled ?? true  // safe default while loading

  const mutation = useMutation({
    mutationFn: (enabled: boolean) =>
      fetch("/trading/kill-switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      }).then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      }),
    onMutate: (enabled: boolean) => {
      const previous = effectiveBotEnabled
      setBotEnabled(enabled)       // optimistic update (D-09)
      return { previous }
    },
    onError: (_err: unknown, _enabled: boolean, context: { previous: boolean } | undefined) => {
      if (context) setBotEnabled(context.previous)  // revert on error
    },
    onSuccess: (data: { bot_enabled: boolean }) => {
      setBotEnabled(data.bot_enabled)  // reconcile with server response
      queryClient.invalidateQueries({ queryKey: ["trading-status"] })
    },
  })

  const isPending = mutation.status === "pending"

  if (effectiveBotEnabled) {
    return (
      <Button
        variant="destructive"
        className="w-full h-9"
        disabled={isPending}
        onClick={() => mutation.mutate(false)}
      >
        {isPending ? <Loader2 size={14} className="animate-spin mr-2" /> : <Square size={14} className="mr-2" />}
        Stop Bot
      </Button>
    )
  }

  return (
    <Button
      className="w-full h-9 bg-green-600 hover:bg-green-700 text-white"
      disabled={isPending}
      onClick={() => mutation.mutate(true)}
    >
      {isPending ? <Loader2 size={14} className="animate-spin mr-2" /> : <Play size={14} className="mr-2" />}
      Start Bot
    </Button>
  )
}
