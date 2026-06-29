"""TTS and image generation API service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from providers.config import get_image_config
from server.errors import redact_known_secrets
from server.media import audio_format_for_path


ImageProviderFactory = Callable[..., Any]


@dataclass(frozen=True)
class MediaFileResult:
    path: str
    media_type: str
    filename: str


class MediaApiServiceUnavailable(RuntimeError):
    """Raised when a required media service is not configured."""


class MediaApiProviderConfigError(RuntimeError):
    """Raised when a media provider cannot be constructed."""


class MediaApiProviderError(RuntimeError):
    """Raised when a media provider call raises."""

    def __init__(self, action: str, original: Exception) -> None:
        super().__init__(str(original))
        self.action = action
        self.original = original


class MediaApiFailedResult(RuntimeError):
    """Raised when a provider returns an explicit failed result."""


def resolve_image_cache_dir(base_dir: str | Path) -> Path:
    """Resolve REST image cache directory from central provider config."""
    image_cfg = get_image_config()
    configured = Path(str(image_cfg.get("cache_dir") or ".cache/image"))
    if configured.is_absolute():
        return configured
    return Path(base_dir) / configured


class MediaApiService:
    """Runs REST media provider calls and returns response-file metadata."""

    def __init__(
        self,
        *,
        tts_engine: Any,
        image_cache_dir: str | Path,
        image_provider_factory: ImageProviderFactory | None = None,
        image_available: bool = True,
        image_unavailable_reason: str = "",
    ) -> None:
        self.tts_engine = tts_engine
        self.image_cache_dir = Path(image_cache_dir)
        self.image_provider_factory = image_provider_factory or self._default_image_provider_factory
        self.image_available = image_available
        self.image_unavailable_reason = image_unavailable_reason

    async def synthesize_tts(
        self,
        *,
        text: str,
        voice: str,
        emotion: str,
    ) -> MediaFileResult:
        if not self.tts_engine:
            raise MediaApiServiceUnavailable("TTS engine is not initialized")

        try:
            result = await self.tts_engine.synthesize(
                text=text,
                voice_preset=voice,
                emotion_instruction=emotion or None,
            )
        except Exception as e:
            print(f"  [tts_api] provider error: {type(e).__name__}: {str(e)[:200]}")
            raise MediaApiProviderError("TTS provider failed", e) from e

        if result.success and result.audio_path:
            audio_format = result.audio_format or audio_format_for_path(result.audio_path)
            return MediaFileResult(
                path=result.audio_path,
                media_type=result.mime_type or "application/octet-stream",
                filename=f"speech.{audio_format}",
            )

        detail = redact_known_secrets(result.error or "TTS provider failed")
        raise MediaApiFailedResult(detail)

    async def generate_image(
        self,
        *,
        prompt: str,
        aspect_ratio: str,
        image_size: str,
    ) -> MediaFileResult:
        if not self.image_available:
            reason = f" (missing {self.image_unavailable_reason})" if self.image_unavailable_reason else ""
            raise MediaApiServiceUnavailable(f"Image provider is not configured{reason}")

        try:
            provider = self.image_provider_factory(cache_dir=str(self.image_cache_dir))
        except ValueError as e:
            raise MediaApiProviderConfigError(str(e)) from e

        try:
            result = await provider.generate(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            )
        except Exception as e:
            print(f"  [image_api] provider error: {type(e).__name__}: {str(e)[:200]}")
            raise MediaApiProviderError("Image provider failed", e) from e

        if result.success and result.image_path:
            ext = os.path.splitext(result.image_path)[1] or ".png"
            return MediaFileResult(
                path=result.image_path,
                media_type=result.mime_type or "image/png",
                filename=f"generated{ext}",
            )

        detail = redact_known_secrets(result.error or "Image generation failed")
        raise MediaApiFailedResult(detail)

    @staticmethod
    def _default_image_provider_factory(**kwargs: Any) -> Any:
        from providers.registry import get_image_gen

        return get_image_gen(**kwargs)
