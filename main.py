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
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Optional, cast

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
from engine.state_store import StateStore
from engine.chat_log_store import ChatLogStore
from memory.memory_store import MemoryStore
from providers.memory.evermemos.evermemos_client import EverMemOSClient
from providers.api_config import get_llm_config, get_tts_config, get_memory_config
from agent.cron_scheduler import CronScheduler
from server.context import AppContext
from server.demo_inject import DemoInjectService
from server.media import audio_format_for_path as _audio_format_for_path
from server.media import media_type_for_file as _media_type_for_file
from server.security import cors_origins_from_env as _cors_origins_from_env
from server.security import request_has_api_token as _request_has_api_token
from server.session_manager import SessionManager
from server.proactive_service import ProactiveService
from server.routes import register_routes
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


def create_app(context: Optional[AppContext] = None) -> FastAPI:
    """Create the FastAPI application and attach its runtime context."""
    server_app = FastAPI(
        title="OpenHer",
        description="AI Companion Server — Genome v10 Hybrid Engine",
        version="0.5.0",
        lifespan=lifespan,
    )
    server_app.state.openher = context or AppContext()
    server_app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins_from_env(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    server_app.middleware("http")(require_api_token)
    register_routes(server_app)
    return server_app


openher_context = AppContext()
app = create_app(openher_context)


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
ws_registry = openher_context.ws_registry
demo_inject_service = cast(DemoInjectService, openher_context.demo_inject_service)
ws_demo_proactive_service = openher_context.ws_demo_proactive_service
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

    openher_context.persona_loader = persona_loader
    openher_context.llm_client = llm_client
    openher_context.tts_engine = tts_engine
    openher_context.task_skill_engine = task_skill_engine
    openher_context.modality_skill_engine = modality_skill_engine
    openher_context.state_store = state_store
    openher_context.chat_log_store = chat_log_store
    openher_context.memory_store = memory_store
    openher_context.evermemos = evermemos
    openher_context.cron_scheduler = cron_scheduler
    openher_context.session_manager = session_manager
    openher_context.proactive_service = proactive_service
    openher_context.ws_demo_command_service = ws_demo_command_service
    openher_context.ws_chat_turn_service = ws_chat_turn_service
    openher_context.persona_switch_service = persona_switch_service
    openher_context.ws_tts_service = ws_tts_service
    openher_context.genome_data_dir = genome_data_dir

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
