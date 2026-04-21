"""Dashboard WebSocket — ConnectionManager singleton and /ws/feed endpoint (Phase 6).

CRITICAL: This module MUST NOT import from analysis/, risk_guard/, or trading/.
The analysis worker imports `manager` from here — one-way dependency only.
Import `manager` (the instance), never `ConnectionManager` (the class) from other modules.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WS client connected — total: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("WS client disconnected — total: %d", len(self.active_connections))

    async def broadcast(self, message: str) -> None:
        """Broadcast to all clients; silently remove dead connections (Pitfall 1)."""
        dead: list[WebSocket] = []
        for ws in self.active_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self.active_connections:
                self.active_connections.remove(ws)


# Module-level singleton — analysis worker imports this instance, not the class.
manager = ConnectionManager()


@router.websocket("/ws/feed")
async def websocket_feed(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive; client sends nothing meaningful
    except WebSocketDisconnect:
        manager.disconnect(websocket)
