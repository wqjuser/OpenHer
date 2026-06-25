"""Route registration for the OpenHer FastAPI app."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from server.routes import chat, demo, health, media, persona, websocket
from server.static import register_spa_routes


def register_routes(app: FastAPI) -> None:
    """Register all HTTP and WebSocket routes on the app."""
    app.include_router(health.router)
    app.include_router(persona.router)
    app.include_router(chat.router)
    app.include_router(media.router)
    app.include_router(demo.router)
    app.include_router(websocket.router)
    register_spa_routes(app, str(Path(__file__).resolve().parents[2]))
