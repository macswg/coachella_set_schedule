import json

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
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    async def broadcast(self, message: str):
        """Broadcast a message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_schedule(self, viewer_html: str, editor_html: str):
        """Broadcast schedule HTML, sending appropriate version to each client."""
        disconnected = []
        for connection, is_editor in self.active_connections.items():
            try:
                html = editor_html if is_editor else viewer_html
                await connection.send_text(html)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_brightness(self, value: int):
        """Broadcast brightness value to all connected clients."""
        self.current_brightness = value
        message = json.dumps({"type": "brightness", "value": value})
        print(f"[Debug] WebSocket broadcast to {len(self.active_connections)} clients: {message}")
        await self.broadcast(message)


# Global connection manager instance
manager = ConnectionManager()
