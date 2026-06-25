"""TTS, image generation, and generated media routes."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from engine.path_security import safe_child_path
from server.context import context_from_request
from server.errors import external_error_detail, redact_known_secrets
from server.media import audio_format_for_path, media_type_for_file


router = APIRouter()
BASE_DIR = Path(__file__).resolve().parents[2]


@router.get("/api/tts")
async def tts_api(
    request: Request,
    text: str = Query(..., description="Text to synthesize"),
    voice: str = Query("sweet_female", description="Voice preset"),
    emotion: str = Query("", description="Emotion instruction"),
):
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    ctx = context_from_request(request)
    if not ctx.tts_engine:
        raise HTTPException(status_code=503, detail="TTS engine is not initialized")
    try:
        result = await ctx.tts_engine.synthesize(
            text=text,
            voice_preset=voice,
            emotion_instruction=emotion or None,
        )
    except Exception as e:
        print(f"  [tts_api] provider error: {type(e).__name__}: {str(e)[:200]}")
        raise HTTPException(
            status_code=502,
            detail=external_error_detail("TTS provider failed", e),
        )

    if result.success and result.audio_path:
        audio_format = result.audio_format or audio_format_for_path(result.audio_path)
        return FileResponse(
            result.audio_path,
            media_type=result.mime_type or "application/octet-stream",
            filename=f"speech.{audio_format}",
        )
    raise HTTPException(
        status_code=502,
        detail=redact_known_secrets(result.error or "TTS provider failed"),
    )


@router.post("/api/image")
async def image_api(
    prompt: str = Query(..., description="Text prompt for image generation"),
    aspect_ratio: str = Query("", description="Aspect ratio (e.g. 16:9, 1:1)"),
    image_size: str = Query("1K", description="Image size (1K, 2K)"),
):
    """Generate an image from a text prompt."""
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    from providers.registry import get_image_gen

    try:
        provider = get_image_gen(cache_dir=str(BASE_DIR / ".cache" / "image"))
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        result = await provider.generate(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
    except Exception as e:
        print(f"  [image_api] provider error: {type(e).__name__}: {str(e)[:200]}")
        raise HTTPException(
            status_code=502,
            detail=external_error_detail("Image provider failed", e),
        )

    if result.success and result.image_path:
        media_type = result.mime_type or "image/png"
        ext = os.path.splitext(result.image_path)[1] or ".png"
        return FileResponse(
            result.image_path,
            media_type=media_type,
            filename=f"generated{ext}",
        )
    raise HTTPException(
        status_code=502,
        detail=redact_known_secrets(result.error or "Image generation failed"),
    )


@router.get("/api/selfie/{filename:path}")
async def serve_selfie(filename: str):
    """Serve a generated selfie image from the cache."""
    selfie_dir = BASE_DIR / ".cache" / "selfie"
    try:
        file_path = safe_child_path(str(selfie_dir), filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid image path")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(str(file_path), media_type=media_type_for_file(str(file_path)))
