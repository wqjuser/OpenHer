"""REST chat turn processing service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

from server.schemas import ChatRequest


class ChatApiServiceUnavailable(RuntimeError):
    """Raised when REST chat cannot run because required services are missing."""


class ChatApiPersonaNotFound(ValueError):
    """Raised when the requested persona or session cannot be created."""


class ChatApiProviderError(RuntimeError):
    """Raised when the underlying chat provider fails."""

    def __init__(self, original: Exception) -> None:
        super().__init__(str(original))
        self.original = original


@dataclass(frozen=True)
class ChatApiResult:
    session_id: str
    response: str
    modality: str
    image_url: Optional[str]
    status: dict[str, Any]

    def to_response(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "response": self.response,
            "modality": self.modality,
            "image_url": self.image_url,
            **self.status,
        }


class ChatApiService:
    """Processes one REST chat turn and assembles the API response."""

    def __init__(
        self,
        *,
        session_manager: Any,
        chat_log_store: Any = None,
    ) -> None:
        self.session_manager = session_manager
        self.chat_log_store = chat_log_store

    async def chat(self, req: ChatRequest) -> ChatApiResult:
        if not self.session_manager:
            raise ChatApiServiceUnavailable("Session manager is not initialized")

        try:
            session_id, agent = self.session_manager.get_or_create(
                req.session_id,
                req.persona_id,
                req.user_name,
                req.client_id,
            )
        except ValueError as e:
            raise ChatApiPersonaNotFound(str(e)) from e

        try:
            result = await agent.chat(req.message)
        except Exception as e:
            print(f"  [chat_api] provider error: {type(e).__name__}: {str(e)[:200]}")
            raise ChatApiProviderError(e) from e

        status = agent.get_status()
        self.session_manager.persist_agent(agent)
        self._save_chat_log(req, result)

        return ChatApiResult(
            session_id=session_id,
            response=result["reply"],
            modality=result["modality"],
            image_url=self._image_url(result.get("image_path")),
            status=status,
        )

    def _save_chat_log(self, req: ChatRequest, result: dict[str, Any]) -> None:
        if not self.chat_log_store or not req.client_id:
            return
        try:
            self.chat_log_store.save_turn(
                client_id=req.client_id,
                persona_id=req.persona_id,
                user_msg=req.message,
                agent_reply=result["reply"],
                modality=result.get("modality", "文字"),
            )
        except Exception as e:
            print(f"  [chat_log] save error: {e}")

    def _image_url(self, image_path: Optional[str]) -> Optional[str]:
        if not image_path:
            return None
        return f"/api/selfie/{os.path.basename(image_path)}"
