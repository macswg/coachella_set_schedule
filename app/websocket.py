import json
from typing import Callable, Optional

from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections for real-time sync between operators."""

    def __init__(self):
        self.active_connections: dict[WebSocket, bool] = {}  # websocket -> is_editor
        self.current_brightness: int = 0

    async def connect(self, websocket: WebSocket, is_editor: bool = False):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[websocket] = is_editor

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.pop(websocket, None)

    async def _send_to_all(self, get_message: Callable[[WebSocket, bool], Optional[str]]):
        """Send messages to all clients, cleaning up disconnected ones."""
        disconnected = []
        for conn, is_editor in self.active_connections.items():
            message = get_message(conn, is_editor)
            if message:
                try:
                    await conn.send_text(message)
                except Exception:
                    disconnected.append(conn)
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast(self, message: str):
        """Broadcast a message to all connected clients."""
        await self._send_to_all(lambda c, e: message)

    async def broadcast_schedule(self, viewer_html: str, editor_html: str):
        """Broadcast schedule HTML, sending appropriate version to each client."""
        await self._send_to_all(lambda c, is_editor: editor_html if is_editor else viewer_html)

    async def broadcast_brightness(self, value: int):
        """Broadcast brightness value to all connected clients."""
        self.current_brightness = value
        await self.broadcast(json.dumps({"type": "brightness", "value": value}))

    async def broadcast_to_editors(self, message: str):
        """Send a message to editor clients only."""
        await self._send_to_all(lambda c, is_editor: message if is_editor else None)

    async def broadcast_reload(self):
        """Tell all connected clients to reload the page."""
        await self.broadcast(json.dumps({"type": "reload"}))

    async def broadcast_recording_state(self, active_reminders: list[str], enabled: bool):
        """Send current recording reminder state to editor clients only."""
        await self.broadcast_to_editors(json.dumps({"type": "recording", "active": active_reminders, "enabled": enabled}))


# Global connection manager instance
manager = ConnectionManager()
