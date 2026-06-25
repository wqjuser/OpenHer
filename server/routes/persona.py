"""Persona metadata and media routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from server.context import context_from_request
from server.persona_api_service import (
    PersonaApiMediaNotFound,
    PersonaApiService,
    PersonaApiServiceUnavailable,
    PersonaApiUnknownMediaType,
)


router = APIRouter()
BASE_DIR = Path(__file__).resolve().parents[2]
PERSONAS_DIR = BASE_DIR / "persona" / "personas"


@router.get("/api/personas")
async def list_personas(request: Request):
    service = _persona_service(request)
    try:
        personas = service.list_personas()
    except PersonaApiServiceUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"personas": [persona.model_dump() for persona in personas]}


@router.get("/api/persona/{persona_id}/media/{media_type}")
async def get_persona_media(persona_id: str, media_type: str, request: Request):
    """Serve persona media from idimage/ directory."""
    service = _persona_service(request)
    try:
        media = service.get_persona_media(persona_id, media_type)
    except PersonaApiUnknownMediaType as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PersonaApiMediaNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return FileResponse(media.path, media_type=media.media_type, filename=media.filename)


@router.get("/api/avatar/{persona_id}")
async def get_avatar(persona_id: str, request: Request):
    """Get static avatar image for a persona."""
    service = _persona_service(request)
    try:
        media = service.get_avatar(persona_id)
    except PersonaApiMediaNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return FileResponse(media.path, media_type=media.media_type, filename=media.filename)


def _persona_service(request: Request) -> PersonaApiService:
    ctx = context_from_request(request)
    return ctx.persona_api_service or PersonaApiService(
        persona_loader=ctx.persona_loader,
        personas_dir=PERSONAS_DIR,
    )
