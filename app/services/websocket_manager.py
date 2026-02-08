"""
WebSocket Manager — Gerencia conexões WebSocket ativas.

Permite broadcast de eventos para todos os clientes conectados,
como atualizações de leads, conversas e mensagens em tempo real.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Gerencia conexões WebSocket ativas e faz broadcast de eventos."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket conectado. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket desconectado. Total: {len(self.active_connections)}")

    async def broadcast(self, event: str, data: dict[str, Any] | None = None) -> None:
        """Envia evento para todos os clientes conectados."""
        message = json.dumps({"event": event, "data": data or {}})
        disconnected: list[WebSocket] = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)

        # Remove conexões que falharam
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_sync_wrapper(self, event: str, data: dict[str, Any] | None = None) -> None:
        """Wrapper para chamar broadcast de contexto síncrono via asyncio."""
        await self.broadcast(event, data)


# Instância singleton
ws_manager = ConnectionManager()
