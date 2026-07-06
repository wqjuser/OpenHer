"""Provider runtime service assembly for OpenHer startup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from providers.api_config import get_image_config, get_llm_config, get_tts_config
from providers.llm import LLMClient
from providers.media.tts_engine import TTSEngine, TTSProvider
from server.media_api_service import MediaApiService, resolve_image_cache_dir
from server.ws_tts import WebSocketTTSService


@dataclass(frozen=True)
class ProviderRuntimeServices:
    llm_client: Any | None
    tts_engine: Any
    tts_available: bool
    ws_tts_service: Any | None
    media_api_service: Any
    warnings: tuple[str, ...]


ProviderFactory = Callable[..., Any]
ImageCacheDirResolver = Callable[[Path], Path]


def build_provider_runtime_services(
    base_dir: Path,
    *,
    llm_config: Mapping[str, Any] | None = None,
    tts_config: Mapping[str, Any] | None = None,
    image_config: Mapping[str, Any] | None = None,
    llm_client_factory: ProviderFactory = LLMClient,
    tts_engine_factory: ProviderFactory = TTSEngine,
    ws_tts_service_factory: ProviderFactory = WebSocketTTSService,
    media_api_service_factory: ProviderFactory = MediaApiService,
    image_cache_dir_resolver: ImageCacheDirResolver = resolve_image_cache_dir,
) -> ProviderRuntimeServices:
    llm_cfg = llm_config or get_llm_config()
    tts_cfg = tts_config or get_tts_config()
    image_cfg = image_config or get_image_config()
    warnings: list[str] = []

    llm_client = None
    if bool(llm_cfg.get("available", True)):
        llm_client = llm_client_factory(
            provider=llm_cfg["provider"],
            model=llm_cfg["model"],
            temperature=llm_cfg.get("temperature", 0.92),
            max_tokens=llm_cfg.get("max_tokens", 1024),
        )
    else:
        warnings.append(
            _provider_unavailable_warning(
                "LLM",
                llm_cfg,
                "已禁用聊天会话、WebSocket 聊天和主动消息",
            )
        )

    tts_engine = tts_engine_factory(
        provider=TTSProvider(str(tts_cfg["provider"])),
        cache_dir=str(Path(base_dir) / str(tts_cfg["cache_dir"])),
    )
    tts_available = bool(tts_cfg.get("available", False))
    ws_tts_service = None
    if tts_available:
        ws_tts_service = ws_tts_service_factory(tts_engine=tts_engine)
    else:
        warnings.append(
            _provider_unavailable_warning(
                "TTS",
                tts_cfg,
                "已禁用语音技能和 WebSocket TTS",
            )
        )

    media_api_service = media_api_service_factory(
        tts_engine=tts_engine if tts_available else None,
        image_cache_dir=image_cache_dir_resolver(Path(base_dir)),
        image_available=bool(image_cfg.get("available", False)),
        image_unavailable_reason=str(image_cfg.get("missing_key_env") or ""),
    )

    return ProviderRuntimeServices(
        llm_client=llm_client,
        tts_engine=tts_engine,
        tts_available=tts_available,
        ws_tts_service=ws_tts_service,
        media_api_service=media_api_service,
        warnings=tuple(warnings),
    )


def _provider_unavailable_warning(label: str, cfg: Mapping[str, Any], consequence: str) -> str:
    provider = str(cfg.get("provider") or "")
    missing_key = str(cfg.get("missing_key_env") or f"{provider.upper()}_API_KEY")
    return f"⚠ {label} provider '{provider}' 未配置 {missing_key}，{consequence}"
