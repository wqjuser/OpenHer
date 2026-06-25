"""Persona API service boundary tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


class FakePersonaLoader:
    def __init__(self, personas: dict[str, Any] | None = None):
        self.personas = personas or {}
        self.load_calls = 0

    def load_all(self) -> dict[str, Any]:
        self.load_calls += 1
        return self.personas


def make_persona(**overrides: Any) -> SimpleNamespace:
    data = {
        "name": "Luna",
        "name_zh": "露娜",
        "age": 24,
        "gender": "female",
        "mbti": "INFP",
        "tags": ["artist"],
        "tags_zh": ["画家"],
        "bio": {"zh": "第一句。第二句。"},
        "personality": "fallback personality",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_persona_api_service_lists_personas_with_media_flags(tmp_path):
    from server.persona_api_service import PersonaApiService

    luna_dir = tmp_path / "luna"
    idimage_dir = luna_dir / "idimage"
    idimage_dir.mkdir(parents=True)
    (luna_dir / "avatar.png").write_bytes(b"avatar")
    (idimage_dir / "front.png").write_bytes(b"front")
    (idimage_dir / "wakening.mp4").write_bytes(b"video")

    loader = FakePersonaLoader({"luna": make_persona()})
    service = PersonaApiService(persona_loader=loader, personas_dir=tmp_path)

    personas = service.list_personas()

    assert loader.load_calls == 1
    assert len(personas) == 1
    persona = personas[0]
    assert persona.persona_id == "luna"
    assert persona.name == "Luna"
    assert persona.name_zh == "露娜"
    assert persona.description == "第一句"
    assert persona.avatar_url == "/api/avatar/luna"
    assert persona.has_front is True
    assert persona.has_awakening_video is True


def test_persona_api_service_uses_description_fallbacks_and_limit(tmp_path):
    from server.persona_api_service import PersonaApiService

    long_personality = "x" * 150
    personas = {
        "bio_en": make_persona(bio={"en": "English first\nsecond"}, personality="ignored"),
        "personality": make_persona(bio={}, personality=long_personality),
    }
    service = PersonaApiService(
        persona_loader=FakePersonaLoader(personas),
        personas_dir=tmp_path,
    )

    result_by_id = {item.persona_id: item for item in service.list_personas()}

    assert result_by_id["bio_en"].description == "English first"
    assert result_by_id["personality"].description == "x" * 120


def test_persona_api_service_resolves_avatar_and_idimage_media(tmp_path):
    from server.persona_api_service import PersonaApiService

    luna_dir = tmp_path / "luna"
    idimage_dir = luna_dir / "idimage"
    idimage_dir.mkdir(parents=True)
    (luna_dir / "avatar.png").write_bytes(b"avatar")
    (idimage_dir / "awakening.mp4").write_bytes(b"awakening")
    (idimage_dir / "wakening.mp4").write_bytes(b"wakening")

    service = PersonaApiService(
        persona_loader=FakePersonaLoader(),
        personas_dir=tmp_path,
    )

    avatar = service.get_avatar("luna")
    awakening = service.get_persona_media("luna", "awakening")
    wakening = service.get_persona_media("luna", "wakening")

    assert avatar.path == str(luna_dir / "avatar.png")
    assert avatar.media_type == "image/png"
    assert avatar.filename == "luna_avatar.png"
    assert awakening.path == str(idimage_dir / "awakening.mp4")
    assert awakening.media_type == "video/mp4"
    assert awakening.filename is None
    assert wakening.path == str(idimage_dir / "wakening.mp4")


def test_persona_api_service_wraps_unavailable_and_media_errors(tmp_path):
    from server.persona_api_service import (
        PersonaApiMediaNotFound,
        PersonaApiService,
        PersonaApiServiceUnavailable,
        PersonaApiUnknownMediaType,
    )

    unavailable_service = PersonaApiService(persona_loader=None, personas_dir=tmp_path)
    try:
        unavailable_service.list_personas()
    except PersonaApiServiceUnavailable as exc:
        assert "Persona loader is not initialized" in str(exc)
    else:
        raise AssertionError("expected PersonaApiServiceUnavailable")

    service = PersonaApiService(persona_loader=FakePersonaLoader(), personas_dir=tmp_path)
    try:
        service.get_persona_media("luna", "profile")
    except PersonaApiUnknownMediaType as exc:
        assert "Unknown media type: profile" in str(exc)
    else:
        raise AssertionError("expected PersonaApiUnknownMediaType")

    try:
        service.get_avatar("luna")
    except PersonaApiMediaNotFound as exc:
        assert "Avatar not found" in str(exc)
    else:
        raise AssertionError("expected PersonaApiMediaNotFound")


def test_persona_routes_delegate_metadata_and_media_to_service_boundary():
    source = (ROOT / "server/routes/persona.py").read_text(encoding="utf-8")
    list_body = source.split("async def list_personas", 1)[1].split("@router.get", 1)[0]
    media_body = source.split("async def get_persona_media", 1)[1].split("@router.get", 1)[0]
    avatar_body = source.split("async def get_avatar", 1)[1]

    assert "from server.persona_api_service import" in source
    assert "PersonaApiService" in source
    assert "service.list_personas()" in list_body
    assert "service.get_persona_media(" in media_body
    assert "service.get_avatar(" in avatar_body
    assert "PersonaInfo" not in source
    assert "import re" not in source
    assert "media_map" not in source


def test_app_context_and_bootstrap_expose_persona_api_service_boundary():
    context_source = (ROOT / "server/context.py").read_text(encoding="utf-8")
    bootstrap_source = (ROOT / "server/bootstrap.py").read_text(encoding="utf-8")

    assert "from server.persona_api_service import PersonaApiService" in context_source
    assert "persona_api_service: PersonaApiService | None = None" in context_source
    assert "from server.persona_api_service import PersonaApiService" in bootstrap_source
    assert "context.persona_api_service = PersonaApiService(" in bootstrap_source
    assert '"persona_api_service": context.persona_api_service' in bootstrap_source
