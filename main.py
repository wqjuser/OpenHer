"""
Gateway — FastAPI WebSocket server for OpenHer (Genome v10 Hybrid).

Provides:
  - WebSocket endpoint for real-time chat with Genome v10 lifecycle
  - REST APIs for persona management, status
  - Agent state persistence (neural network weights + drive metabolism)
  - Session auto-cleanup with TTL
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Optional, cast

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

import uuid as _uuid

from persona import PersonaLoader
from providers.llm import LLMClient
from agent.chat_agent import ChatAgent
from providers.media.tts_engine import TTSEngine, TTSProvider
from agent.skills import TaskSkillEngine, ModalitySkillEngine
from agent.skills.tool_registry import ToolRegistry
from agent.skills.tools.photo_tools import register_photo_tools
from agent.skills.tools.voice_tools import register_voice_tools
from agent.skills.tools.split_tools import register_split_tools
from engine.path_security import safe_child_path
from engine.state_store import StateStore
from engine.chat_log_store import ChatLogStore
from memory.memory_store import MemoryStore
from providers.memory.evermemos.evermemos_client import EverMemOSClient
from providers.api_config import get_llm_config, get_tts_config, get_memory_config
from agent.cron_scheduler import CronScheduler
from engine.genome import DRIVE_LABELS
from server.errors import external_error_detail as _external_error_detail
from server.errors import redact_known_secrets as _redact_known_secrets
from server.demo_inject import (
    DemoClientNotConnected,
    DemoInjectSendFailed,
    DemoInjectService,
    MissingDemoInjectFields,
)
from server.media import audio_format_for_path as _audio_format_for_path
from server.media import media_type_for_file as _media_type_for_file
from server.schemas import ChatRequest, PersonaInfo
from server.security import cors_origins_from_env as _cors_origins_from_env
from server.security import request_has_api_token as _request_has_api_token
from server.session_manager import SessionManager
from server.proactive_service import ProactiveService, default_proactive_metrics
from server.static import register_spa_routes
from server.websocket_registry import WebSocketConnectionRegistry
from server.websocket_chat import WebSocketChatTurnService
from server.websocket_persona_switch import WebSocketPersonaSwitchService
from server.websocket_demo import WebSocketDemoCommandService, WebSocketDemoProactiveService
from server.ws_tts import WebSocketTTSService

# ──────────────────────────────────────────────────────────────
# Load env
# ──────────────────────────────────────────────────────────────

load_dotenv(override=True)  # override=True: .env values take precedence over shell exports


# ──────────────────────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_app: FastAPI):
    await startup()
    try:
        yield
    finally:
        await shutdown()


app = FastAPI(
    title="OpenHer",
    description="AI Companion Server — Genome v10 Hybrid Engine",
    version="0.5.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins_from_env(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_api_token(request: Request, call_next):
    """Require a bearer token when OPENHER_API_TOKEN is configured."""
    if request.method == "OPTIONS":
        return await call_next(request)
    if not _request_has_api_token(
        request.headers.get("Authorization"),
        request.query_params.get("token"),
    ):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


# ──────────────────────────────────────────────────────────────
# Global services (initialized at startup)
# ──────────────────────────────────────────────────────────────

persona_loader: PersonaLoader = cast(PersonaLoader, None)
llm_client: LLMClient = cast(LLMClient, None)
tts_engine: TTSEngine = cast(TTSEngine, None)
task_skill_engine: TaskSkillEngine = cast(TaskSkillEngine, None)
modality_skill_engine: ModalitySkillEngine = cast(ModalitySkillEngine, None)
state_store: StateStore = cast(StateStore, None)
chat_log_store: ChatLogStore = cast(ChatLogStore, None)
memory_store: MemoryStore = cast(MemoryStore, None)
evermemos: EverMemOSClient = cast(EverMemOSClient, None)
cron_scheduler: CronScheduler = cast(CronScheduler, None)
session_manager: SessionManager = cast(SessionManager, None)
proactive_service: ProactiveService = cast(ProactiveService, None)
ws_registry = WebSocketConnectionRegistry()
demo_inject_service = DemoInjectService(ws_registry)
ws_demo_proactive_service = WebSocketDemoProactiveService()
ws_demo_command_service: WebSocketDemoCommandService = cast(WebSocketDemoCommandService, None)
ws_chat_turn_service: WebSocketChatTurnService = cast(WebSocketChatTurnService, None)
persona_switch_service: WebSocketPersonaSwitchService = cast(WebSocketPersonaSwitchService, None)
ws_tts_service: WebSocketTTSService = cast(WebSocketTTSService, None)
genome_data_dir: str = ""

# Session TTL: auto-clean sessions older than 30 minutes
SESSION_TTL_SECONDS = 30 * 60

# Proactive heartbeat
_proactive_task: Optional[asyncio.Task] = None
_INSTANCE_ID = str(_uuid.uuid4())[:8]  # unique per server instance
_PROACTIVE_INTERVAL = 300  # seconds between heartbeat sweeps

async def startup():
    """Initialize all services on server start."""
    global persona_loader, llm_client, tts_engine, task_skill_engine, modality_skill_engine
    global state_store, chat_log_store, memory_store, evermemos, cron_scheduler, genome_data_dir
    global session_manager, proactive_service, persona_switch_service, ws_tts_service, ws_chat_turn_service
    global ws_demo_command_service

    base_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. Load personas
    persona_loader = PersonaLoader(os.path.join(base_dir, "persona", "personas"))
    personas = persona_loader.load_all()
    print(f"✓ 加载了 {len(personas)} 个角色: {list(personas.keys())}")

    # 2. Create LLM client (config/api.yaml → env var override)
    llm_cfg = get_llm_config()
    llm_client = LLMClient(
        provider=llm_cfg["provider"],
        model=llm_cfg["model"],
        temperature=llm_cfg.get("temperature", 0.92),
        max_tokens=llm_cfg.get("max_tokens", 1024),
    )

    # 3. Create TTS engine (config/api.yaml → env var override)
    tts_cfg = get_tts_config()
    tts_available = bool(tts_cfg.get("available", False))
    tts_engine = TTSEngine(
        provider=TTSProvider(tts_cfg["provider"]),
        cache_dir=os.path.join(base_dir, tts_cfg["cache_dir"]),
        openai_api_key=tts_cfg["api_keys"].get("openai"),
        dashscope_api_key=tts_cfg["api_keys"].get("dashscope"),
        minimax_api_key=tts_cfg["api_keys"].get("minimax"),
        minimax_model=tts_cfg.get("minimax_model", "speech-2.8-turbo"),
    )
    if tts_available:
        ws_tts_service = WebSocketTTSService(tts_engine=tts_engine)
    else:
        ws_tts_service = cast(WebSocketTTSService, None)
        missing_key = tts_cfg.get("missing_key_env") or f"{tts_cfg['provider'].upper()}_API_KEY"
        print(
            f"⚠ TTS provider '{tts_cfg['provider']}' 未配置 {missing_key}，"
            "已禁用语音技能和 WebSocket TTS"
        )

    # 4. Load skills (dual engine architecture)
    tool_registry = ToolRegistry()
    register_photo_tools(tool_registry)
    if tts_available:
        register_voice_tools(tool_registry)
    register_split_tools(tool_registry)
    print(f"✓ 注册了 {len(tool_registry.tool_names)} 个工具: {tool_registry.tool_names}")

    task_skill_engine = TaskSkillEngine(os.path.join(base_dir, "skills", "task"), tool_registry=tool_registry)
    task_loaded = task_skill_engine.load_all()
    modality_skill_engine = ModalitySkillEngine(
        os.path.join(base_dir, "skills", "modality"),
        tool_registry=tool_registry,
    )
    modality_loaded = modality_skill_engine.load_all()
    cron_skills = task_skill_engine.get_cron_skills()
    print(f"✓ 加载了 {len(task_loaded)}+{len(modality_loaded)} 个技能 (task+modality), {len(cron_skills)} 个定时任务")

    # 5. Data directories
    data_dir = os.path.join(base_dir, ".data")
    genome_data_dir = os.path.join(data_dir, "genome")
    os.makedirs(genome_data_dir, exist_ok=True)

    # 6. State persistence
    state_store = StateStore(os.path.join(data_dir, "openher.db"))

    # 6b. Chat log persistence (display-only, independent from engine state)
    chat_log_store = ChatLogStore(os.path.join(data_dir, "chat.db"))

    # 7. Memory store (config/api.yaml → memory.soulmem.db_path)
    from providers.config import get_memory_provider_config
    _mem_prov_cfg = get_memory_provider_config()
    _soulmem_db = os.path.join(base_dir, _mem_prov_cfg["soulmem"]["db_path"])
    os.makedirs(os.path.dirname(_soulmem_db) or ".", exist_ok=True)
    memory_store = MemoryStore(_soulmem_db)

    # 7b. EverMemOS long-term memory (config/api.yaml → env var override)
    mem_cfg = get_memory_config()
    if mem_cfg["enabled"] and (mem_cfg["base_url"] or mem_cfg["api_key"]):
        evermemos = EverMemOSClient(
            base_url=mem_cfg["base_url"] or None,
            api_key=mem_cfg["api_key"] or None,
        )
        if evermemos.available:
            await evermemos.verify_connection()
    else:
        evermemos = cast(EverMemOSClient, None)
        print("ℹ EverMemOS: 未配置或已禁用，使用本地 MemoryStore")

    session_manager = SessionManager(
        persona_loader=persona_loader,
        llm_client=llm_client,
        task_skill_engine=task_skill_engine,
        modality_skill_engine=modality_skill_engine,
        memory_store=memory_store,
        state_store=state_store,
        evermemos=evermemos,
        genome_data_dir=genome_data_dir,
        ttl_seconds=SESSION_TTL_SECONDS,
    )
    persona_switch_service = WebSocketPersonaSwitchService(
        registry=ws_registry,
        get_or_create_session=get_or_create_session,
        remove_session=remove_session,
    )
    ws_chat_turn_service = WebSocketChatTurnService(
        registry=ws_registry,
        get_or_create_session=get_or_create_session,
        chat_log_store=chat_log_store,
    )
    ws_demo_command_service = WebSocketDemoCommandService(
        get_or_create_session=get_or_create_session,
        presets_file=os.path.join(base_dir, "demo", "presets", "showcase.yaml"),
        proactive_delivery=ws_demo_proactive_service,
    )

    # 8. Cron scheduler
    if cron_skills:
        cron_scheduler = CronScheduler()
        cron_scheduler.set_message_generator(_cron_generate_message)
        cron_scheduler.set_message_callback(_cron_deliver_message)
        cron_scheduler.register_skills(cron_skills, persona_ids=list(personas.keys()))
        cron_scheduler.start()

    # 9. Load proactive config + start heartbeat loop
    global _proactive_task
    try:
        import yaml as _yaml_cfg
        from pathlib import Path as _PathCfg
        _cfg_path = _PathCfg(base_dir) / "providers" / "memory" / "evermemos" / "memory_config.yaml"
        _cfg_raw = _yaml_cfg.safe_load(_cfg_path.read_text()).get("evermemos", {}) if _cfg_path.exists() else {}
    except Exception:
        _cfg_raw = {}
    proactive_config = {
        'cooldown_hours': _cfg_raw.get('proactive_cooldown_hours', 4),
        'max_pending': _cfg_raw.get('proactive_max_pending', 3),
        'lock_ttl': _cfg_raw.get('proactive_lock_ttl_sec', 600),
    }
    proactive_service = ProactiveService(
        state_store=state_store,
        session_manager=session_manager,
        evermemos=evermemos,
        ws_connections=ws_registry.session_connections,
        persist_agent=_persist_agent,
        instance_id=_INSTANCE_ID,
        config=proactive_config,
        interval_seconds=_PROACTIVE_INTERVAL,
    )
    _proactive_task = asyncio.create_task(proactive_service.heartbeat_loop())
    print(f"✓ 主动消息心跳已启动 (cooldown={proactive_config['cooldown_hours']}h, ttl={proactive_config['lock_ttl']}s)")

    print("✓ OpenHer 服务启动完成 (v0.5.0 — Genome v10 Hybrid Engine)")


async def shutdown():
    """Save all active sessions and close DBs."""
    # Stop proactive heartbeat
    if _proactive_task and not _proactive_task.done():
        _proactive_task.cancel()
        try:
            await _proactive_task
        except asyncio.CancelledError:
            pass
    if cron_scheduler:
        cron_scheduler.stop()
    if state_store:
        if session_manager:
            session_manager.persist_all()
        state_store.close()
    if memory_store:
        memory_store.close()
    if chat_log_store:
        chat_log_store.close()
    # Flush EverMemOS for all active sessions
    if evermemos and evermemos.available:
        tasks = [
            evermemos.close_session(
                user_id=agent.evermemos_uid,
                persona_id=agent.persona.persona_id,
                group_id=agent._group_id,
            )
            for agent in session_manager.active_agents()
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    print("✓ 状态已保存，服务关闭")


# ──────────────────────────────────────────────────────────────
# Cron message generation + delivery
# ──────────────────────────────────────────────────────────────

async def _cron_generate_message(skill_prompt: str, persona_id: str) -> str:
    """Generate a proactive cron message using an isolated ChatAgent."""
    persona = persona_loader.get(persona_id)
    if not persona:
        return ""
    from providers.llm.client import ChatMessage
    messages = [
        ChatMessage(role="system", content=f"你是{persona.name}。{skill_prompt}"),
        ChatMessage(role="user", content="请生成一条主动消息"),
    ]
    response = await llm_client.chat(messages)
    return response.content


async def _cron_deliver_message(persona_id: str, skill_id: str, message: str) -> None:
    """Deliver a cron message — store in memory for next session."""
    print(f"[cron] 📨 {persona_id}/{skill_id}: {message[:60]}...")
    if memory_store:
        memory_store.add(
            user_id="__broadcast__",
            persona_id=persona_id,
            content=f"[{skill_id}] {message}",
            category="event",
            importance=0.6,
        )


# ──────────────────────────────────────────────────────────────
# Proactive Heartbeat — Drive-driven autonomous messaging
# ──────────────────────────────────────────────────────────────

async def _proactive_heartbeat_loop():
    """Compatibility wrapper for the proactive service loop."""
    if not proactive_service:
        return
    await proactive_service.heartbeat_loop()


async def _proactive_sweep():
    """Compatibility wrapper for one proactive service sweep."""
    if proactive_service:
        await proactive_service.sweep()


async def _deliver_proactive_msg(agent: ChatAgent, session_id: str, row: dict):
    """Compatibility wrapper for proactive service delivery."""
    if not proactive_service:
        raise RuntimeError("Proactive service is not initialized")
    await proactive_service.deliver_message(agent, session_id, row)


@app.get("/api/proactive/metrics")
async def proactive_metrics():
    """Proactive messaging observability: rates and counters."""
    if proactive_service:
        return proactive_service.metrics_snapshot()
    return default_proactive_metrics()


# ── Serve React SPA ──
register_spa_routes(app, os.path.dirname(os.path.abspath(__file__)))


# ──────────────────────────────────────────────────────────────
# Message Protocol
# ──────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────
# Session Management (with TTL + persistence)
# ──────────────────────────────────────────────────────────────

def _persist_agent(agent: ChatAgent) -> None:
    """Compatibility wrapper for session-manager persistence."""
    if session_manager:
        session_manager.persist_agent(agent)


def _cleanup_expired_sessions() -> int:
    """Compatibility wrapper for session-manager TTL cleanup."""
    return session_manager.cleanup_expired_sessions() if session_manager else 0


def get_or_create_session(
    session_id: Optional[str],
    persona_id: str,
    user_name: Optional[str] = None,
    client_id: Optional[str] = None,
) -> tuple[str, ChatAgent]:
    """Compatibility wrapper for session-manager get-or-create."""
    if not session_manager:
        raise RuntimeError("Session manager is not initialized")
    return session_manager.get_or_create(session_id, persona_id, user_name, client_id)


def remove_session(session_id: str) -> None:
    """Compatibility wrapper for session-manager removal."""
    if session_manager:
        session_manager.remove(session_id)


# ──────────────────────────────────────────────────────────────
# REST API Endpoints
# ──────────────────────────────────────────────────────────────

@app.get("/api/status")
async def api_status():
    return {
        "name": "OpenHer",
        "version": "0.5.0",
        "engine": "Genome v10",
        "status": "running",
        "personas": persona_loader.list_ids() if persona_loader else [],
        "active_sessions": session_manager.active_count if session_manager else 0,
    }


@app.get("/api/personas")
async def list_personas():
    personas = persona_loader.load_all()
    result = []
    import re as _re_bio
    _personas_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "persona", "personas")
    for pid, p in personas.items():
        # Check for static avatar.png
        _avatar_path = os.path.join(_personas_dir, pid, "avatar.png")
        _has_avatar = os.path.isfile(_avatar_path)
        # Extract first sentence only (YAML `>` folds multi-line bio into one string)
        _raw_bio = p.bio.get("zh") or p.bio.get("en") or p.personality or ""
        _first_sentence = _re_bio.split(r'[。！？\n]', _raw_bio)[0].strip()
        # Check idimage/ for media assets
        _idimage_dir = os.path.join(_personas_dir, pid, "idimage")
        _has_front = os.path.isfile(os.path.join(_idimage_dir, "front.png"))
        _has_video = any(
            os.path.isfile(os.path.join(_idimage_dir, v))
            for v in ("awakening.mp4", "wakening.mp4")
        )
        result.append(PersonaInfo(
            persona_id=pid,
            name=p.name,
            name_zh=p.name_zh,
            age=p.age,
            gender=p.gender,
            mbti=p.mbti,
            tags=p.tags,
            tags_zh=p.tags_zh,
            description=_first_sentence[:120],
            avatar_url=f"/api/avatar/{pid}" if _has_avatar else None,
            has_front=_has_front,
            has_awakening_video=_has_video,
        ))
    return {"personas": [r.model_dump() for r in result]}


@app.get("/api/persona/{persona_id}/media/{media_type}")
async def get_persona_media(persona_id: str, media_type: str):
    """
    Serve persona media from idimage/ directory.
    media_type: 'front', 'awakened', 'awakening'
    """
    _media_map = {
        "front": [("front.png", "image/png")],
        "face": [("face.png", "image/png")],
        "awakened": [("awakened.png", "image/png")],
        "awakening": [("awakening.mp4", "video/mp4"), ("wakening.mp4", "video/mp4")],
        "wakening": [("wakening.mp4", "video/mp4")],
    }
    if media_type not in _media_map:
        raise HTTPException(status_code=400, detail=f"Unknown media type: {media_type}")
    _personas_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "persona", "personas")
    for filename, _mime in _media_map[media_type]:
        file_path = os.path.join(_personas_dir, persona_id, "idimage", filename)
        if os.path.isfile(file_path):
            return FileResponse(file_path, media_type=_media_type_for_file(file_path))
    raise HTTPException(status_code=404, detail=f"Media not found: {persona_id}/{media_type}")


@app.post("/api/chat")
async def chat_api(req: ChatRequest):
    try:
        session_id, agent = get_or_create_session(
            req.session_id, req.persona_id, req.user_name, req.client_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        result = await agent.chat(req.message)
    except Exception as e:
        print(f"  [chat_api] provider error: {type(e).__name__}: {str(e)[:200]}")
        raise HTTPException(
            status_code=502,
            detail=_external_error_detail("Chat provider failed", e),
        )

    status = agent.get_status()

    _persist_agent(agent)

    # Chat log: display-layer persistence (no engine impact)
    if chat_log_store and req.client_id:
        try:
            chat_log_store.save_turn(
                client_id=req.client_id,
                persona_id=req.persona_id,
                user_msg=req.message,
                agent_reply=result['reply'],
                modality=result.get('modality', '文字'),
            )
        except Exception as e:
            print(f"  [chat_log] save error: {e}")

    return {
        "session_id": session_id,
        "response": result['reply'],
        "modality": result['modality'],
        "image_url": f"/api/selfie/{os.path.basename(result['image_path'])}" if result.get('image_path') else None,
        **status,
    }


@app.get("/api/session/{session_id}/status")
async def session_status(session_id: str):
    entry = session_manager.get_entry(session_id) if session_manager else None
    if not entry:
        raise HTTPException(status_code=404, detail="Session not found")
    agent, _ = entry
    return agent.get_status()


@app.get("/api/chat/history/{persona_id}")
async def get_chat_history(
    persona_id: str,
    client_id: str = Query(..., description="Frontend client identity (localStorage UUID)"),
    limit: int = Query(50, ge=1, le=500),
    before_id: int = Query(None, description="Pagination cursor — return messages before this id"),
):
    """Load chat history for display. Does not affect engine state."""
    if not chat_log_store:
        return {"messages": [], "total": 0}
    messages = chat_log_store.load_messages(client_id, persona_id, limit, before_id)
    total = chat_log_store.count_messages(client_id, persona_id)
    return {"messages": messages, "total": total}


@app.get("/api/tts")
async def tts_api(
    text: str = Query(..., description="Text to synthesize"),
    voice: str = Query("sweet_female", description="Voice preset"),
    emotion: str = Query("", description="Emotion instruction"),
):
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    try:
        result = await tts_engine.synthesize(
            text=text,
            voice_preset=voice,
            emotion_instruction=emotion or None,
        )
    except Exception as e:
        print(f"  [tts_api] provider error: {type(e).__name__}: {str(e)[:200]}")
        raise HTTPException(
            status_code=502,
            detail=_external_error_detail("TTS provider failed", e),
        )

    if result.success and result.audio_path:
        audio_format = result.audio_format or _audio_format_for_path(result.audio_path)
        return FileResponse(
            result.audio_path,
            media_type=result.mime_type or "application/octet-stream",
            filename=f"speech.{audio_format}",
        )
    else:
        raise HTTPException(
            status_code=502,
            detail=_redact_known_secrets(result.error or "TTS provider failed"),
        )


# ──────────────────────────────────────────────────────────────
# Demo Remote Control API — script → HTTP → UI WS
# ──────────────────────────────────────────────────────────────

@app.post("/api/demo/inject")
async def demo_inject(request: Request):
    """Push a demo command to the UI client via WS.
    Body: {"client_id": "...", "action": "send_chat|switch_persona|scenario|time_jump",
           "content": "...", "persona_id": "..."}
    """
    body = await request.json()
    try:
        result = await demo_inject_service.send(body)
        print(f"  [demo-inject] ✅ {body.get('action')} → 1 UI client")
        return result
    except MissingDemoInjectFields:
        raise HTTPException(status_code=400, detail="client_id and action required")
    except DemoClientNotConnected as e:
        raise HTTPException(status_code=404, detail=f"No WS for client_id {e.client_id[:12]}")
    except DemoInjectSendFailed as e:
        print(f"  [demo-inject] ❌ {body.get('action')} failed: {e}")
        raise HTTPException(status_code=502, detail="WS send failed")


# ──────────────────────────────────────────────────────────────
# Image Generation API
# ──────────────────────────────────────────────────────────────

@app.post("/api/image")
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
        provider = get_image_gen(
            cache_dir=os.path.join(
                os.path.dirname(os.path.abspath(__file__)), ".cache", "image"
            ),
        )
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
            detail=_external_error_detail("Image provider failed", e),
        )

    if result.success and result.image_path:
        # Determine media type
        media_type = result.mime_type or "image/png"
        ext = os.path.splitext(result.image_path)[1] or ".png"
        return FileResponse(
            result.image_path,
            media_type=media_type,
            filename=f"generated{ext}",
        )
    else:
        raise HTTPException(
            status_code=502,
            detail=_redact_known_secrets(result.error or "Image generation failed"),
        )


@app.get("/api/selfie/{filename:path}")
async def serve_selfie(filename: str):
    """Serve a generated selfie image from the cache."""
    selfie_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "selfie")
    try:
        file_path = safe_child_path(selfie_dir, filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid image path")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(file_path, media_type=_media_type_for_file(file_path))


# ──────────────────────────────────────────────────────────────
# Avatar — Static file serving only (no generation)
# ──────────────────────────────────────────────────────────────


@app.get("/api/avatar/{persona_id}")
async def get_avatar(persona_id: str):
    """Get static avatar image for a persona."""
    _personas_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "persona", "personas")
    path = os.path.join(_personas_dir, persona_id, "avatar.png")
    if os.path.isfile(path):
        return FileResponse(path, media_type=_media_type_for_file(path), filename=f"{persona_id}_avatar.png")
    raise HTTPException(status_code=404, detail="Avatar not found")


# ──────────────────────────────────────────────────────────────
# WebSocket Endpoint — Real-time chat with Genome v10
# ──────────────────────────────────────────────────────────────

@app.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    """
    WebSocket endpoint for real-time persona chat with Genome v10.

    Protocol:
      Client → Server: {"type": "chat", "content": "hello", "persona_id": "vivian"}
      Server → Client: {"type": "chat_start", "session_id": "abc123"}
      Server → Client: {"type": "chat_chunk", "content": "嘿～"}  (streamed)
      Server → Client: {"type": "chat_end", "dominant_drive": "🔗 联结", ...}
    """
    if not _request_has_api_token(
        ws.headers.get("Authorization"),
        ws.query_params.get("token"),
    ):
        await ws.close(code=1008)
        return
    await ws.accept()
    session_id = None
    agent = None

    # ── Typing debounce state ──
    _msg_buffer: list[dict] = []        # buffered chat messages
    _typing_active: bool = False        # client is typing
    _debounce_task: asyncio.Task | None = None  # grace period timer
    _connection_closed: bool = False
    DEBOUNCE_GRACE_SEC = 2.0            # wait after cursor leaves input
    DEBOUNCE_FALLBACK_SEC = 3.0         # fallback if no typing signal

    async def _flush_buffer():
        """Merge buffered messages and process as single turn."""
        nonlocal _msg_buffer, _debounce_task, agent, session_id
        if _connection_closed:
            _msg_buffer = []
            _debounce_task = None
            return
        if not _msg_buffer:
            return

        # Take all buffered messages
        msgs = _msg_buffer
        _msg_buffer = []
        _debounce_task = None

        if ws_chat_turn_service:
            result = await ws_chat_turn_service.handle_messages(
                websocket=ws,
                messages=msgs,
                agent=agent,
                session_id=session_id,
            )
            session_id = result.session_id
            agent = result.agent

    async def _schedule_flush(delay: float):
        """Schedule a flush after delay, cancelling any existing timer."""
        nonlocal _debounce_task
        if _debounce_task and not _debounce_task.done():
            _debounce_task.cancel()
        async def _wait_and_flush():
            try:
                await asyncio.sleep(delay)
                if _connection_closed:
                    return
                await _flush_buffer()
            except asyncio.CancelledError:
                raise
            except RuntimeError as e:
                print(f"[ws] flush skipped after connection close: {e}")
            except Exception as e:
                print(f"[ws] flush task error: {type(e).__name__}: {e}")
        _debounce_task = asyncio.create_task(_wait_and_flush())

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "content": "Invalid JSON"})
                continue

            msg_type = msg.get("type", "")

            # Early client_id registration for demo inject API
            _cid = msg.get("client_id")
            if _cid:
                ws_registry.register_client(_cid, ws)

            # ── Typing indicator (informational only) ──
            if msg_type == "typing":
                _typing_active = msg.get("active", False)
                print(f"  [debounce] typing={'active' if _typing_active else 'inactive'}, buffer={len(_msg_buffer)}")
                # When user explicitly leaves input and buffer has messages,
                # schedule a faster flush (2s instead of 3s fallback)
                if not _typing_active and _msg_buffer:
                    await _schedule_flush(DEBOUNCE_GRACE_SEC)
                    print(f"  [debounce] ⏱ scheduled flush in {DEBOUNCE_GRACE_SEC}s")
                continue

            # ── Chat message ──
            if msg_type == "chat":
                text = msg.get("content", "").strip()
                if not text:
                    continue

                # Buffer the message and schedule flush
                _msg_buffer.append(msg)
                print(f"  [debounce] 📥 buffered msg #{len(_msg_buffer)}: '{text[:30]}', typing_active={_typing_active}")

                # Always use 3s debounce for chat messages.
                # The faster 1s flush only triggers via explicit typing:false signal.
                await _schedule_flush(DEBOUNCE_FALLBACK_SEC)

            # ── TTS request ──
            elif msg_type == "tts_request":
                if ws_tts_service:
                    await ws_tts_service.handle_request(ws, agent, msg.get("content", ""))

            # ── Status request ──
            elif msg_type == "status":
                if agent:
                    await ws.send_json({
                        "type": "status",
                        **agent.get_status(),
                    })

            # ── Switch persona ──
            elif msg_type == "switch_persona":
                if persona_switch_service:
                    switch_result = await persona_switch_service.switch(
                        websocket=ws,
                        current_session_id=session_id,
                        persona_id=msg.get("persona_id", ""),
                        user_name=msg.get("user_name"),
                        client_id=msg.get("client_id"),
                    )
                    if switch_result:
                        session_id, agent = switch_result

            # ── Demo commands ──
            elif msg_type.startswith("demo_"):
                if ws_demo_command_service:
                    demo_result = await ws_demo_command_service.handle(
                        websocket=ws,
                        message=msg,
                        agent=agent,
                        session_id=session_id,
                    )
                    if demo_result.handled:
                        session_id = demo_result.session_id
                        agent = demo_result.agent

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[ws] 未预期异常: {type(e).__name__}: {e}")
        try:
            await ws.send_json({"type": "error", "content": f"服务端异常: {str(e)[:200]}"})
        except Exception:
            pass
    finally:
        _connection_closed = True
        if _debounce_task and not _debounce_task.done():
            _debounce_task.cancel()
            try:
                await _debounce_task
            except asyncio.CancelledError:
                pass
        _msg_buffer.clear()
        # Deregister WS connection
        ws_registry.unregister_websocket(ws)
        if session_id:
            remove_session(session_id)
        print(f"[ws] 连接关闭: session={session_id}")
