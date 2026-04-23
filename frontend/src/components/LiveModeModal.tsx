import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"

const LIVE_PHRASE = "ENABLE LIVE TRADING"
const PAPER_PHRASE = "ENABLE PAPER TRADING"

interface LiveModeModalProps {
  isLive: boolean
  open: boolean
  onClose: () => void
}

export function LiveModeModal({ isLive, open, onClose }: LiveModeModalProps) {
  const [input, setInput] = useState("")
  const [error, setError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const targetPhrase = isLive ? PAPER_PHRASE : LIVE_PHRASE
  const targetMode: "paper" | "live" = isLive ? "paper" : "live"
  const isMatch = input === targetPhrase  // exact case-sensitive match (D-09, D-10)

  const modeMutation = useMutation({
    mutationFn: () => api.setMode(targetMode),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio-mode"] })
      setInput("")
      setError(null)
      onClose()
    },
    onError: () => {
      setError("Failed to switch mode. Try again.")
    },
  })

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      // Reset input state when modal closes
      setInput("")
      setError(null)
      onClose()
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            Switch to {targetMode === "live" ? "LIVE" : "PAPER"} Trading
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-3">
          {/* Warning — paper→live only */}
          {!isLive && (
            <p className="text-sm text-muted-foreground">
              This will use real money. All trades will be placed on your live Alpaca account.
            </p>
          )}

          <p className="text-sm text-muted-foreground">
            Type{" "}
            <code className="font-mono font-semibold">{targetPhrase}</code>{" "}
            to confirm.
          </p>

          <Input
            value={input}
            onChange={(e) => {
              setInput(e.target.value)
              setError(null)
            }}
            placeholder={targetPhrase}
            autoComplete="off"
          />

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            {isLive ? "Keep LIVE mode" : "Keep PAPER mode"}
          </Button>
          <Button
            variant={targetMode === "live" ? "destructive" : "default"}
            disabled={!isMatch || modeMutation.isPending}
            onClick={() => modeMutation.mutate()}
          >
            Confirm
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
