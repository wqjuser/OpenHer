"""WebSocket persona switching workflow."""

from __future__ import annotations

from typing import Any, Callable, Optional

from server.websocket_registry import WebSocketConnectionRegistry


class WebSocketPersonaSwitchService:
    """Switches one WebSocket from its current session to a new persona session."""

    def __init__(
        self,
        *,
        registry: WebSocketConnectionRegistry,
        get_or_create_session: Callable[[Optional[str], str, Optional[str], Optional[str]], tuple[str, Any]],
        remove_session: Callable[[str], None],
    ) -> None:
        self.registry = registry
        self.get_or_create_session = get_or_create_session
        self.remove_session = remove_session

    async def switch(
        self,
        *,
        websocket: Any,
        current_session_id: Optional[str],
        persona_id: str,
        user_name: Optional[str],
        client_id: Optional[str],
    ) -> Optional[tuple[str, Any]]:
        if not persona_id:
            return None

        if current_session_id:
            self.registry.unregister_session(current_session_id, websocket)
            self.remove_session(current_session_id)

        try:
            session_id, agent = self.get_or_create_session(
                None,
                persona_id,
                user_name,
                client_id,
            )
        except ValueError as e:
            await websocket.send_json({"type": "error", "content": str(e)})
            return None

        self.registry.register_session(session_id, websocket)
        await websocket.send_json({
            "type": "persona_switched",
            "session_id": session_id,
            "persona": agent.persona.name,
        })
        return session_id, agent
