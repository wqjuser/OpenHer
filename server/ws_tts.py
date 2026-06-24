"""WebSocket TTS request handling."""

from __future__ import annotations

import base64
from typing import Any, Callable, Optional

from providers.media.tts_engine import TTSEngine
from server.media import audio_format_for_path


def voice_preset_from_config(persona_id: str) -> str:
    """Resolve a provider-specific voice preset for a persona."""
    from providers.config import _load as _load_config

    tts_cfg = _load_config().get("tts", {})
    voice_map = tts_cfg.get("voice_map", {})
    default_voice = tts_cfg.get("providers", {}).get(
        tts_cfg.get("provider", ""), {}
    ).get("default_voice", "Cherry")
    return voice_map.get(persona_id, default_voice)


class WebSocketTTSService:
    """Synthesizes ad-hoc TTS requests and sends them over WebSocket."""

    def __init__(
        self,
        *,
        tts_engine: TTSEngine,
        voice_resolver: Optional[Callable[[str], str]] = None,
    ) -> None:
        self.tts_engine = tts_engine
        self.voice_resolver = voice_resolver or voice_preset_from_config

    async def handle_request(self, websocket: Any, agent: Any, text: str) -> None:
        """Handle one ``tts_request`` message; no-op when text or agent is missing."""
        if not text or not agent:
            return

        try:
            voice_preset = self.voice_resolver(agent.persona.persona_id)
            result = await self.tts_engine.synthesize(
                text=text,
                voice_preset=voice_preset,
            )
            if result.success and result.audio_path:
                with open(result.audio_path, "rb") as f:
                    audio_b64 = base64.b64encode(f.read()).decode()
                await websocket.send_json({
                    "type": "tts_audio",
                    "audio": audio_b64,
                    "format": result.audio_format or audio_format_for_path(result.audio_path),
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "content": f"TTS 失败: {result.error}",
                })
        except Exception as e:
            await websocket.send_json({
                "type": "error",
                "content": f"TTS 异常: {str(e)[:200]}",
            })
