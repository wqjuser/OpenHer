"""Provider runtime assembly boundary tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class FakeService:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def test_provider_runtime_builds_available_services_with_injected_factories(tmp_path):
    from server.provider_runtime import build_provider_runtime_services

    llm_calls: list[dict[str, Any]] = []
    tts_calls: list[dict[str, Any]] = []
    ws_calls: list[dict[str, Any]] = []
    media_calls: list[dict[str, Any]] = []

    def llm_factory(**kwargs: Any) -> FakeService:
        llm_calls.append(kwargs)
        return FakeService(**kwargs)

    def tts_factory(**kwargs: Any) -> FakeService:
        tts_calls.append(kwargs)
        return FakeService(**kwargs)

    def ws_factory(**kwargs: Any) -> FakeService:
        ws_calls.append(kwargs)
        return FakeService(**kwargs)

    def media_factory(**kwargs: Any) -> FakeService:
        media_calls.append(kwargs)
        return FakeService(**kwargs)

    runtime = build_provider_runtime_services(
        tmp_path,
        llm_config={
            "provider": "deepseek",
            "model": "deepseek-chat",
            "available": True,
            "temperature": 0.2,
            "max_tokens": 256,
        },
        tts_config={
            "provider": "dashscope",
            "cache_dir": ".cache/tts",
            "available": True,
            "missing_key_env": "",
        },
        image_config={
            "available": True,
            "missing_key_env": "",
        },
        llm_client_factory=llm_factory,
        tts_engine_factory=tts_factory,
        ws_tts_service_factory=ws_factory,
        media_api_service_factory=media_factory,
        image_cache_dir_resolver=lambda base_dir: Path(base_dir) / ".cache/image",
    )

    assert llm_calls == [
        {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "temperature": 0.2,
            "max_tokens": 256,
        }
    ]
    assert tts_calls[0]["provider"].value == "dashscope"
    assert tts_calls[0]["cache_dir"] == str(tmp_path / ".cache/tts")
    assert ws_calls == [{"tts_engine": runtime.tts_engine}]
    assert media_calls == [
        {
            "tts_engine": runtime.tts_engine,
            "image_cache_dir": tmp_path / ".cache/image",
            "image_available": True,
            "image_unavailable_reason": "",
        }
    ]
    assert runtime.llm_client is not None
    assert runtime.tts_available is True
    assert runtime.ws_tts_service is not None
    assert runtime.media_api_service is not None
    assert runtime.warnings == ()


def test_provider_runtime_degrades_unavailable_llm_tts_and_image(tmp_path):
    from server.provider_runtime import build_provider_runtime_services

    llm_calls: list[dict[str, Any]] = []
    ws_calls: list[dict[str, Any]] = []
    media_calls: list[dict[str, Any]] = []

    def tts_factory(**kwargs: Any) -> FakeService:
        return FakeService(**kwargs)

    def media_factory(**kwargs: Any) -> FakeService:
        media_calls.append(kwargs)
        return FakeService(**kwargs)

    runtime = build_provider_runtime_services(
        tmp_path,
        llm_config={
            "provider": "deepseek",
            "model": "deepseek-chat",
            "available": False,
            "missing_key_env": "DEEPSEEK_API_KEY or LLM_API_KEY",
        },
        tts_config={
            "provider": "dashscope",
            "cache_dir": ".cache/tts",
            "available": False,
            "missing_key_env": "DASHSCOPE_API_KEY or TTS_API_KEY",
        },
        image_config={
            "available": False,
            "missing_key_env": "GEMINI_API_KEY or IMAGE_API_KEY",
        },
        llm_client_factory=lambda **kwargs: llm_calls.append(kwargs),
        tts_engine_factory=tts_factory,
        ws_tts_service_factory=lambda **kwargs: ws_calls.append(kwargs),
        media_api_service_factory=media_factory,
        image_cache_dir_resolver=lambda base_dir: Path(base_dir) / ".cache/image",
    )

    assert llm_calls == []
    assert ws_calls == []
    assert runtime.llm_client is None
    assert runtime.tts_engine is not None
    assert runtime.tts_available is False
    assert runtime.ws_tts_service is None
    assert media_calls[0]["tts_engine"] is None
    assert media_calls[0]["image_available"] is False
    assert media_calls[0]["image_unavailable_reason"] == "GEMINI_API_KEY or IMAGE_API_KEY"
    assert runtime.warnings == (
        "⚠ LLM provider 'deepseek' 未配置 DEEPSEEK_API_KEY or LLM_API_KEY，已禁用聊天会话、WebSocket 聊天和主动消息",
        "⚠ TTS provider 'dashscope' 未配置 DASHSCOPE_API_KEY or TTS_API_KEY，已禁用语音技能和 WebSocket TTS",
    )
