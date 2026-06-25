"""Demo remote-control HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from server.context import context_from_request
from server.demo_inject import (
    DemoClientNotConnected,
    DemoInjectSendFailed,
    MissingDemoInjectFields,
)


router = APIRouter()


@router.post("/api/demo/inject")
async def demo_inject(request: Request):
    """Push a demo command to the UI client via WS."""
    ctx = context_from_request(request)
    body = await request.json()
    try:
        result = await ctx.demo_inject_service.send(body)
        print(f"  [demo-inject] ✅ {body.get('action')} → 1 UI client")
        return result
    except MissingDemoInjectFields:
        raise HTTPException(status_code=400, detail="client_id and action required")
    except DemoClientNotConnected as e:
        raise HTTPException(status_code=404, detail=f"No WS for client_id {e.client_id[:12]}")
    except DemoInjectSendFailed as e:
        print(f"  [demo-inject] ❌ {body.get('action')} failed: {e}")
        raise HTTPException(status_code=502, detail="WS send failed")
