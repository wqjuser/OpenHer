"""Persona metadata and media lookup API service."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.path_security import safe_child_path
from server.media import media_type_for_file
from server.schemas import PersonaInfo


@dataclass(frozen=True)
class PersonaMediaFile:
    path: str
    media_type: str
    filename: str | None = None


class PersonaApiServiceUnavailable(RuntimeError):
    """Raised when persona metadata cannot be loaded."""


class PersonaApiUnknownMediaType(ValueError):
    """Raised when a requested persona media type is unsupported."""


class PersonaApiMediaNotFound(FileNotFoundError):
    """Raised when a persona media file does not exist."""


class PersonaApiService:
    """Builds persona API responses and resolves persona media files."""

    MEDIA_MAP = {
        "front": ("front.png",),
        "face": ("face.png",),
        "awakened": ("awakened.png",),
        "awakening": ("awakening.mp4", "wakening.mp4"),
        "wakening": ("wakening.mp4",),
    }

    def __init__(self, *, persona_loader: Any, personas_dir: str | Path) -> None:
        self.persona_loader = persona_loader
        self.personas_dir = Path(personas_dir)

    def list_personas(self) -> list[PersonaInfo]:
        if not self.persona_loader:
            raise PersonaApiServiceUnavailable("Persona loader is not initialized")

        personas = self.persona_loader.load_all()
        result: list[PersonaInfo] = []
        for persona_id, persona in personas.items():
            avatar_path = self._persona_file(persona_id, "avatar.png")
            idimage_dir = self._persona_file(persona_id, "idimage")
            result.append(PersonaInfo(
                persona_id=persona_id,
                name=getattr(persona, "name", persona_id),
                name_zh=getattr(persona, "name_zh", None),
                age=getattr(persona, "age", None),
                gender=getattr(persona, "gender", "female"),
                mbti=getattr(persona, "mbti", None),
                tags=getattr(persona, "tags", []),
                tags_zh=getattr(persona, "tags_zh", []),
                description=self._description_for(persona),
                avatar_url=f"/api/avatar/{persona_id}" if avatar_path.is_file() else None,
                has_front=(idimage_dir / "front.png").is_file(),
                has_awakening_video=any(
                    (idimage_dir / filename).is_file()
                    for filename in ("awakening.mp4", "wakening.mp4")
                ),
            ))
        return result

    def get_persona_media(self, persona_id: str, media_type: str) -> PersonaMediaFile:
        filenames = self.MEDIA_MAP.get(media_type)
        if not filenames:
            raise PersonaApiUnknownMediaType(f"Unknown media type: {media_type}")

        for filename in filenames:
            file_path = self._persona_file(persona_id, f"idimage/{filename}")
            if file_path.is_file():
                return PersonaMediaFile(
                    path=str(file_path),
                    media_type=media_type_for_file(str(file_path)),
                )
        raise PersonaApiMediaNotFound(f"Media not found: {persona_id}/{media_type}")

    def get_avatar(self, persona_id: str) -> PersonaMediaFile:
        file_path = self._persona_file(persona_id, "avatar.png")
        if not file_path.is_file():
            raise PersonaApiMediaNotFound("Avatar not found")
        return PersonaMediaFile(
            path=str(file_path),
            media_type=media_type_for_file(str(file_path)),
            filename=f"{persona_id}_avatar.png",
        )

    def _persona_file(self, persona_id: str, child_path: str) -> Path:
        try:
            return safe_child_path(self.personas_dir, f"{persona_id}/{child_path}")
        except ValueError as e:
            raise PersonaApiMediaNotFound("Media not found") from e

    @staticmethod
    def _description_for(persona: Any) -> str:
        bio = getattr(persona, "bio", {})
        if isinstance(bio, dict):
            raw_bio = bio.get("zh") or bio.get("en") or ""
        else:
            raw_bio = str(bio)
        raw_description = raw_bio or getattr(persona, "personality", "") or ""
        return re.split(r"[。！？\n]", raw_description)[0].strip()[:120]
