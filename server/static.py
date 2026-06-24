"""Static SPA route registration for the FastAPI server."""

from __future__ import annotations

import os

from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles


def register_spa_routes(app, base_dir: str) -> None:
    """Register built Web UI static asset and fallback routes."""
    static_dir = os.path.join(base_dir, "static")
    assets_dir = os.path.join(static_dir, "assets")

    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/app", include_in_schema=False)
    @app.get("/discover", include_in_schema=False)
    @app.get("/chat/{path:path}", include_in_schema=False)
    async def serve_spa(path: str = ""):
        """Serve React SPA — all frontend routes return index.html."""
        html_path = os.path.join(static_dir, "index.html")
        if not os.path.exists(html_path):
            return HTMLResponse("<h1>Please run: cd web && npm run build</h1>", status_code=503)
        return HTMLResponse(open(html_path, encoding="utf-8").read())
