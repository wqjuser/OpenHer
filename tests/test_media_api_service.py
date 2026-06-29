"""Media API service boundary tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class FakeTtsEngine:
    def __init__(self, result: Any):
        self.result = result
        self.calls: list[dict[str, Any]] = []

    async def synthesize(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.result


class FakeImageProvider:
    def __init__(self, result: Any):
        self.result = result
        self.calls: list[dict[str, Any]] = []

    async def generate(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.result


async def test_media_api_service_synthesizes_tts_file_result():
    from server.media_api_service import MediaApiService

    tts_result = SimpleNamespace(
        success=True,
        audio_path="/tmp/speech.wav",
        audio_format="wav",
        mime_type="audio/wav",
        error="",
    )
    tts_engine = FakeTtsEngine(tts_result)
    service = MediaApiService(
        tts_engine=tts_engine,
        image_cache_dir=Path("/tmp/image-cache"),
    )

    result = await service.synthesize_tts(
        text="hello",
        voice="sweet_female",
        emotion="happy",
    )

    assert tts_engine.calls == [{
        "text": "hello",
        "voice_preset": "sweet_female",
        "emotion_instruction": "happy",
    }]
    assert result.path == "/tmp/speech.wav"
    assert result.media_type == "audio/wav"
    assert result.filename == "speech.wav"


async def test_media_api_service_generates_image_file_result(tmp_path):
    from server.media_api_service import MediaApiService

    image_result = SimpleNamespace(
        success=True,
        image_path="/tmp/generated.webp",
        mime_type="image/webp",
        error="",
    )
    provider = FakeImageProvider(image_result)
    factory_calls: list[dict[str, Any]] = []

    def fake_image_factory(**kwargs: Any) -> FakeImageProvider:
        factory_calls.append(kwargs)
        return provider

    service = MediaApiService(
        tts_engine=None,
        image_cache_dir=tmp_path / "image-cache",
        image_provider_factory=fake_image_factory,
    )

    result = await service.generate_image(
        prompt="portrait",
        aspect_ratio="1:1",
        image_size="1K",
    )

    assert factory_calls == [{"cache_dir": str(tmp_path / "image-cache")}]
    assert provider.calls == [{
        "prompt": "portrait",
        "aspect_ratio": "1:1",
        "image_size": "1K",
    }]
    assert result.path == "/tmp/generated.webp"
    assert result.media_type == "image/webp"
    assert result.filename == "generated.webp"


def test_resolve_image_cache_dir_uses_central_image_config(tmp_path):
    from server.media_api_service import resolve_image_cache_dir

    with patch(
        "server.media_api_service.get_image_config",
        return_value={"cache_dir": "custom/image-cache"},
    ):
        assert resolve_image_cache_dir(tmp_path) == tmp_path / "custom/image-cache"

    absolute_cache = tmp_path / "absolute-image-cache"
    with patch(
        "server.media_api_service.get_image_config",
        return_value={"cache_dir": str(absolute_cache)},
    ):
        assert resolve_image_cache_dir(tmp_path / "repo") == absolute_cache


async def test_media_api_service_wraps_missing_tts_engine_and_provider_failures(tmp_path):
    from server.media_api_service import (
        MediaApiFailedResult,
        MediaApiProviderError,
        MediaApiService,
        MediaApiServiceUnavailable,
    )

    service = MediaApiService(tts_engine=None, image_cache_dir=tmp_path)

    try:
        await service.synthesize_tts(text="hello", voice="sweet_female", emotion="")
    except MediaApiServiceUnavailable as exc:
        assert "TTS engine is not initialized" in str(exc)
    else:
        raise AssertionError("expected MediaApiServiceUnavailable")

    failed_tts = FakeTtsEngine(SimpleNamespace(
        success=False,
        audio_path=None,
        audio_format=None,
        mime_type=None,
        error="provider rejected request secret-token-123",
    ))
    failed_service = MediaApiService(tts_engine=failed_tts, image_cache_dir=tmp_path)
    try:
        await failed_service.synthesize_tts(text="hello", voice="sweet_female", emotion="")
    except MediaApiFailedResult as exc:
        assert "provider rejected request" in str(exc)
    else:
        raise AssertionError("expected MediaApiFailedResult")

    class ExplodingProvider:
        async def generate(self, **_kwargs: Any) -> Any:
            raise RuntimeError("image unavailable")

    provider_service = MediaApiService(
        tts_engine=None,
        image_cache_dir=tmp_path,
        image_provider_factory=lambda **_kwargs: ExplodingProvider(),
    )
    try:
        await provider_service.generate_image(prompt="portrait", aspect_ratio="", image_size="1K")
    except MediaApiProviderError as exc:
        assert exc.action == "Image provider failed"
        assert isinstance(exc.original, RuntimeError)
    else:
        raise AssertionError("expected MediaApiProviderError")


def test_media_routes_delegate_tts_and_image_generation_to_service_boundary():
    source = (ROOT / "server/routes/media.py").read_text(encoding="utf-8")
    tts_body = source.split("async def tts_api", 1)[1].split("@router.post", 1)[0]
    image_body = source.split("async def image_api", 1)[1].split("@router.get", 1)[0]

    assert "from server.media_api_service import" in source
    assert "MediaApiService" in source
    assert "resolve_image_cache_dir" in source
    assert "result = await service.synthesize_tts(" in tts_body
    assert "result = await service.generate_image(" in image_body
    assert "ctx.tts_engine.synthesize(" not in tts_body
    assert "provider.generate(" not in image_body
    assert "get_image_gen" not in image_body
    assert "redact_known_secrets" not in source
    assert 'BASE_DIR / ".cache" / "image"' not in source


def test_app_context_and_bootstrap_expose_media_api_service_boundary():
    context_source = (ROOT / "server/context.py").read_text(encoding="utf-8")
    bootstrap_source = (ROOT / "server/bootstrap.py").read_text(encoding="utf-8")

    assert "from server.media_api_service import MediaApiService" in context_source
    assert "media_api_service: MediaApiService | None = None" in context_source
    assert "from server.media_api_service import MediaApiService" in bootstrap_source
    assert "resolve_image_cache_dir" in bootstrap_source
    assert "context.media_api_service = MediaApiService(" in bootstrap_source
    assert "tts_engine=context.tts_engine if tts_available else None" in bootstrap_source
    assert '"media_api_service": context.media_api_service' in bootstrap_source
    assert 'base_dir / ".cache" / "image"' not in bootstrap_source
