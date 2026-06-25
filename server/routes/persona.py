"""Persona metadata and media routes."""

from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from server.context import context_from_request
from server.media import media_type_for_file
from server.schemas import PersonaInfo


router = APIRouter()
BASE_DIR = Path(__file__).resolve().parents[2]
PERSONAS_DIR = BASE_DIR / "persona" / "personas"


@router.get("/api/personas")
async def list_personas(request: Request):
    ctx = context_from_request(request)
    if not ctx.persona_loader:
        raise HTTPException(status_code=503, detail="Persona loader is not initialized")
    personas = ctx.persona_loader.load_all()
    result = []
    for pid, p in personas.items():
        avatar_path = PERSONAS_DIR / pid / "avatar.png"
        idimage_dir = PERSONAS_DIR / pid / "idimage"
        raw_bio = p.bio.get("zh") or p.bio.get("en") or p.personality or ""
        first_sentence = re.split(r"[。！？\n]", raw_bio)[0].strip()
        has_front = (idimage_dir / "front.png").is_file()
        has_video = any((idimage_dir / v).is_file() for v in ("awakening.mp4", "wakening.mp4"))
        result.append(PersonaInfo(
            persona_id=pid,
            name=p.name,
            name_zh=p.name_zh,
            age=p.age,
            gender=p.gender,
            mbti=p.mbti,
            tags=p.tags,
            tags_zh=p.tags_zh,
            description=first_sentence[:120],
            avatar_url=f"/api/avatar/{pid}" if avatar_path.is_file() else None,
            has_front=has_front,
            has_awakening_video=has_video,
        ))
    return {"personas": [r.model_dump() for r in result]}


@router.get("/api/persona/{persona_id}/media/{media_type}")
async def get_persona_media(persona_id: str, media_type: str):
    """Serve persona media from idimage/ directory."""
    media_map = {
        "front": [("front.png", "image/png")],
        "face": [("face.png", "image/png")],
        "awakened": [("awakened.png", "image/png")],
        "awakening": [("awakening.mp4", "video/mp4"), ("wakening.mp4", "video/mp4")],
        "wakening": [("wakening.mp4", "video/mp4")],
    }
    if media_type not in media_map:
        raise HTTPException(status_code=400, detail=f"Unknown media type: {media_type}")
    for filename, _mime in media_map[media_type]:
        file_path = PERSONAS_DIR / persona_id / "idimage" / filename
        if file_path.is_file():
            return FileResponse(str(file_path), media_type=media_type_for_file(str(file_path)))
    raise HTTPException(status_code=404, detail=f"Media not found: {persona_id}/{media_type}")


@router.get("/api/avatar/{persona_id}")
async def get_avatar(persona_id: str):
    """Get static avatar image for a persona."""
    path = PERSONAS_DIR / persona_id / "avatar.png"
    if path.is_file():
        return FileResponse(
            str(path),
            media_type=media_type_for_file(str(path)),
            filename=f"{persona_id}_avatar.png",
        )
    raise HTTPException(status_code=404, detail="Avatar not found")
