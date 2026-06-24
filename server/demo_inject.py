"""Demo remote-control message forwarding."""

from __future__ import annotations

from typing import Any, Mapping

from server.websocket_registry import WebSocketConnectionRegistry


class DemoInjectError(Exception):
    """Base error for demo inject forwarding failures."""


class MissingDemoInjectFields(DemoInjectError):
    """Raised when client_id or action is missing."""


class DemoClientNotConnected(DemoInjectError):
    """Raised when no active WebSocket is registered for a client."""

    def __init__(self, client_id: str) -> None:
        self.client_id = client_id
        super().__init__(client_id)


class DemoInjectSendFailed(DemoInjectError):
    """Raised when the target WebSocket cannot receive the command."""


class DemoInjectService:
    """Builds and forwards script-driven demo commands to the latest UI socket."""

    def __init__(self, registry: WebSocketConnectionRegistry) -> None:
        self.registry = registry

    async def send(self, body: Mapping[str, Any]) -> dict[str, bool | int]:
        client_id = body.get("client_id")
        action = body.get("action")
        if not client_id or not action:
            raise MissingDemoInjectFields("client_id and action required")

        target_ws = self.registry.latest_client(str(client_id))
        if not target_ws:
            raise DemoClientNotConnected(str(client_id))

        inject_msg = {
            "type": "demo_inject",
            "action": action,
            "content": body.get("content", ""),
            "persona_id": body.get("persona_id", ""),
            "scenario_id": body.get("scenario_id", ""),
            "hours": body.get("hours", 0),
            "tab": body.get("tab", 0),
            "category": body.get("category", ""),
        }

        try:
            await target_ws.send_json(inject_msg)
        except Exception as exc:
            self.registry.unregister_client(str(client_id))
            raise DemoInjectSendFailed("WS send failed") from exc

        return {"ok": True, "sent_to": 1}
