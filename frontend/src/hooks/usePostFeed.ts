import { useState, useEffect, useRef, useCallback } from "react"
import type { PostFeedMessage } from "@/lib/api"

export type ConnectionStatus = "connected" | "reconnecting" | "disconnected"

export function usePostFeed() {
  const [posts, setPosts] = useState<PostFeedMessage[]>([])
  const [status, setStatus] = useState<ConnectionStatus>("disconnected")
  const wsRef = useRef<WebSocket | null>(null)
  const retryDelayRef = useRef(1000)
  const unmountedRef = useRef(false)

  const connect = useCallback(() => {
    if (unmountedRef.current) return

    const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:"
    const wsHost = window.location.host || "localhost:8000"
    // Dev mode (Vite on :5173) needs to point to backend directly; prod uses same-origin via Nginx
    const isDevHost = wsHost.includes(":5173")
    const wsUrl = isDevHost
      ? "ws://localhost:8000/ws/feed"
      : `${wsProto}//${wsHost}/ws/feed`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      if (unmountedRef.current) return
      setStatus("connected")
      retryDelayRef.current = 1000  // reset backoff on successful connect
    }

    ws.onmessage = (event: MessageEvent) => {
      if (unmountedRef.current) return
      try {
        const msg: PostFeedMessage = JSON.parse(event.data)
        setPosts(prev => [msg, ...prev])  // prepend — newest at top (D-06)
      } catch {
        // Ignore malformed messages
      }
    }

    ws.onclose = () => {
      if (unmountedRef.current) return
      setStatus("reconnecting")
      const delay = Math.min(retryDelayRef.current, 30_000)
      retryDelayRef.current = delay * 2  // exponential backoff, cap at 30s
      setTimeout(connect, delay)
    }

    ws.onerror = () => {
      // onclose fires after onerror — reconnect handled there
    }
  }, [])

  useEffect(() => {
    unmountedRef.current = false
    connect()
    return () => {
      unmountedRef.current = true
      wsRef.current?.close()
    }
  }, [connect])

  return { posts, status }
}
