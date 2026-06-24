"""Connection indexes for active WebSocket clients."""

from __future__ import annotations

from typing import Any, Optional


class WebSocketConnectionRegistry:
    """Tracks active sockets by session and latest socket by client id."""

    def __init__(self) -> None:
        self.session_connections: dict[str, set[Any]] = {}
        self.client_connections: dict[str, Any] = {}

    def register_session(self, session_id: str, websocket: Any) -> None:
        self.session_connections.setdefault(session_id, set()).add(websocket)

    def unregister_session(self, session_id: str, websocket: Any) -> None:
        peers = self.session_connections.get(session_id)
        if not peers:
            return
        peers.discard(websocket)
        if not peers:
            del self.session_connections[session_id]

    def connections_for_session(self, session_id: str) -> set[Any]:
        return set(self.session_connections.get(session_id, set()))

    def register_client(self, client_id: str, websocket: Any) -> None:
        self.client_connections[client_id] = websocket

    def latest_client(self, client_id: str) -> Optional[Any]:
        return self.client_connections.get(client_id)

    def unregister_client(self, client_id: str) -> None:
        self.client_connections.pop(client_id, None)

    def unregister_websocket(self, websocket: Any) -> None:
        for session_id in list(self.session_connections):
            self.unregister_session(session_id, websocket)
        for client_id, client_ws in list(self.client_connections.items()):
            if client_ws is websocket:
                del self.client_connections[client_id]
