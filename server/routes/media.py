"""TTS, image generation, and generated media routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from engine.path_security import safe_child_path
from server.context import context_from_request
from server.errors import external_error_detail
from server.media import media_type_for_file
from server.media_api_service import (
    MediaApiFailedResult,
    MediaApiProviderConfigError,
    MediaApiProviderError,
    MediaApiService,
    MediaApiServiceUnavailable,
)


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
    service = ctx.media_api_service or MediaApiService(
        tts_engine=ctx.tts_engine,
        image_cache_dir=BASE_DIR / ".cache" / "image",
    )
    try:
        result = await service.synthesize_tts(
            text=text,
            voice=voice,
            emotion=emotion,
        )
    except MediaApiServiceUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except MediaApiProviderError as e:
        raise HTTPException(
            status_code=502,
            detail=external_error_detail(e.action, e.original),
        ) from e
    except MediaApiFailedResult as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return FileResponse(result.path, media_type=result.media_type, filename=result.filename)


@router.post("/api/image")
async def image_api(
    request: Request,
    prompt: str = Query(..., description="Text prompt for image generation"),
    aspect_ratio: str = Query("", description="Aspect ratio (e.g. 16:9, 1:1)"),
    image_size: str = Query("1K", description="Image size (1K, 2K)"),
):
    """Generate an image from a text prompt."""
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    ctx = context_from_request(request)
    service = ctx.media_api_service or MediaApiService(
        tts_engine=ctx.tts_engine,
        image_cache_dir=BASE_DIR / ".cache" / "image",
    )
    try:
        result = await service.generate_image(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
    except MediaApiProviderConfigError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except MediaApiProviderError as e:
        raise HTTPException(
            status_code=502,
            detail=external_error_detail(e.action, e.original),
        ) from e
    except MediaApiFailedResult as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return FileResponse(result.path, media_type=result.media_type, filename=result.filename)


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
