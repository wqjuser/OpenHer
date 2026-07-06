"""Runtime service assembly for the OpenHer FastAPI application."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any, Optional

from agent.chat_agent import ChatAgent
from agent.cron_scheduler import CronScheduler
from agent.skills import ModalitySkillEngine, TaskSkillEngine
from agent.skills.tool_registry import ToolRegistry
from agent.skills.tools.photo_tools import register_photo_tools
from agent.skills.tools.split_tools import register_split_tools
from agent.skills.tools.voice_tools import register_voice_tools
from persona import PersonaLoader
from server.chat_api_service import ChatApiService
from server.context import AppContext
from server.persistence_runtime import build_persistence_runtime_services
from server.persona_api_service import PersonaApiService
from server.provider_runtime import build_provider_runtime_services
from server.proactive_service import ProactiveService
from server.session_agent_factory import SessionAgentFactory
from server.session_manager import SessionManager
from server.websocket_chat import WebSocketChatTurnService
from server.websocket_demo import WebSocketDemoCommandService
from server.websocket_persona_switch import WebSocketPersonaSwitchService
from server.websocket_route_service import WebSocketRouteService


SESSION_TTL_SECONDS = 30 * 60
PROACTIVE_INTERVAL_SECONDS = 300
INSTANCE_ID = str(uuid.uuid4())[:8]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _get_or_create_session(
    context: AppContext,
    session_id: Optional[str],
    persona_id: str,
    user_name: Optional[str] = None,
    client_id: Optional[str] = None,
) -> tuple[str, ChatAgent]:
    if not context.session_manager:
        raise RuntimeError("Session manager is not initialized")
    return context.session_manager.get_or_create(session_id, persona_id, user_name, client_id)


def _remove_session(context: AppContext, session_id: str) -> None:
    if context.session_manager:
        context.session_manager.remove(session_id)


def _persist_agent(context: AppContext, agent: ChatAgent) -> None:
    if context.session_manager:
        context.session_manager.persist_agent(agent)


async def _cron_generate_message(context: AppContext, skill_prompt: str, persona_id: str) -> str:
    if not context.persona_loader or not context.llm_client:
        return ""
    persona = context.persona_loader.get(persona_id)
    if not persona:
        return ""

    from providers.llm.client import ChatMessage

    messages = [
        ChatMessage(role="system", content=f"你是{persona.name}。{skill_prompt}"),
        ChatMessage(role="user", content="请生成一条主动消息"),
    ]
    response = await context.llm_client.chat(messages)
    return response.content


async def _cron_deliver_message(
    context: AppContext,
    persona_id: str,
    skill_id: str,
    message: str,
) -> None:
    print(f"[cron] 📨 {persona_id}/{skill_id}: {message[:60]}...")
    if context.memory_store:
        context.memory_store.add(
            user_id="__broadcast__",
            persona_id=persona_id,
            content=f"[{skill_id}] {message}",
            category="event",
            importance=0.6,
        )


def _load_proactive_config(base_dir: Path) -> dict[str, Any]:
    try:
        import yaml as yaml_cfg

        cfg_path = base_dir / "providers" / "memory" / "evermemos" / "memory_config.yaml"
        cfg_raw = yaml_cfg.safe_load(cfg_path.read_text()).get("evermemos", {}) if cfg_path.exists() else {}
    except Exception:
        cfg_raw = {}
    return {
        "cooldown_hours": cfg_raw.get("proactive_cooldown_hours", 4),
        "max_pending": cfg_raw.get("proactive_max_pending", 3),
        "lock_ttl": cfg_raw.get("proactive_lock_ttl_sec", 600),
    }


async def startup(context: AppContext) -> None:
    """Initialize all runtime services on server start."""
    base_dir = _repo_root()

    context.persona_loader = PersonaLoader(str(base_dir / "persona" / "personas"))
    personas = context.persona_loader.load_all()
    print(f"✓ 加载了 {len(personas)} 个角色: {list(personas.keys())}")
    context.persona_api_service = PersonaApiService(
        persona_loader=context.persona_loader,
        personas_dir=base_dir / "persona" / "personas",
    )

    provider_runtime = build_provider_runtime_services(base_dir)
    context.llm_client = provider_runtime.llm_client
    context.tts_engine = provider_runtime.tts_engine
    context.ws_tts_service = provider_runtime.ws_tts_service
    context.media_api_service = provider_runtime.media_api_service
    for warning in provider_runtime.warnings:
        print(warning)

    tool_registry = ToolRegistry()
    register_photo_tools(tool_registry)
    if provider_runtime.tts_available:
        register_voice_tools(tool_registry)
    register_split_tools(tool_registry)
    print(f"✓ 注册了 {len(tool_registry.tool_names)} 个工具: {tool_registry.tool_names}")

    context.task_skill_engine = TaskSkillEngine(str(base_dir / "skills" / "task"), tool_registry=tool_registry)
    task_loaded = context.task_skill_engine.load_all()
    context.modality_skill_engine = ModalitySkillEngine(
        str(base_dir / "skills" / "modality"),
        tool_registry=tool_registry,
    )
    modality_loaded = context.modality_skill_engine.load_all()
    cron_skills = context.task_skill_engine.get_cron_skills()
    print(f"✓ 加载了 {len(task_loaded)}+{len(modality_loaded)} 个技能 (task+modality), {len(cron_skills)} 个定时任务")

    persistence_runtime = await build_persistence_runtime_services(base_dir)
    context.genome_data_dir = str(persistence_runtime.genome_data_dir)
    context.state_store = persistence_runtime.state_store
    context.chat_log_store = persistence_runtime.chat_log_store
    context.memory_store = persistence_runtime.memory_store
    context.evermemos = persistence_runtime.evermemos
    for message in persistence_runtime.messages:
        print(message)
    state_store = persistence_runtime.state_store
    chat_log_store = persistence_runtime.chat_log_store
    memory_store = persistence_runtime.memory_store
    evermemos = persistence_runtime.evermemos

    if context.llm_client:
        context.session_agent_factory = SessionAgentFactory(
            persona_loader=context.persona_loader,
            llm_client=context.llm_client,
            task_skill_engine=context.task_skill_engine,
            modality_skill_engine=context.modality_skill_engine,
            memory_store=memory_store,
            state_store=state_store,
            evermemos=evermemos,
            genome_data_dir=context.genome_data_dir,
        )
        context.session_manager = SessionManager(
            agent_factory=context.session_agent_factory,
            state_store=state_store,
            evermemos=evermemos,
            ttl_seconds=SESSION_TTL_SECONDS,
        )
        context.chat_api_service = ChatApiService(
            session_manager=context.session_manager,
            chat_log_store=chat_log_store,
        )

        context.persona_switch_service = WebSocketPersonaSwitchService(
            registry=context.ws_registry,
            get_or_create_session=lambda session_id, persona_id, user_name=None, client_id=None: _get_or_create_session(
                context, session_id, persona_id, user_name, client_id
            ),
            remove_session=lambda session_id: _remove_session(context, session_id),
        )
        context.ws_chat_turn_service = WebSocketChatTurnService(
            registry=context.ws_registry,
            get_or_create_session=lambda session_id, persona_id, user_name=None, client_id=None: _get_or_create_session(
                context, session_id, persona_id, user_name, client_id
            ),
            chat_log_store=context.chat_log_store,
        )
        context.ws_demo_command_service = WebSocketDemoCommandService(
            get_or_create_session=lambda session_id, persona_id, user_name=None, client_id=None: _get_or_create_session(
                context, session_id, persona_id, user_name, client_id
            ),
            presets_file=str(base_dir / "demo" / "presets" / "showcase.yaml"),
            proactive_delivery=context.ws_demo_proactive_service,
        )
    else:
        context.session_agent_factory = None
        context.session_manager = None
        context.chat_api_service = ChatApiService(
            session_manager=None,
            chat_log_store=chat_log_store,
        )
        context.persona_switch_service = None
        context.ws_chat_turn_service = None
        context.ws_demo_command_service = None

    context.ws_route_service = WebSocketRouteService(
        registry=context.ws_registry,
        session_manager=context.session_manager,
        chat_turn_service=context.ws_chat_turn_service,
        tts_service=context.ws_tts_service,
        persona_switch_service=context.persona_switch_service,
        demo_command_service=context.ws_demo_command_service,
    )

    if context.llm_client and context.session_manager:
        if cron_skills:
            context.cron_scheduler = CronScheduler()
            context.cron_scheduler.set_message_generator(
                lambda skill_prompt, persona_id: _cron_generate_message(context, skill_prompt, persona_id)
            )
            context.cron_scheduler.set_message_callback(
                lambda persona_id, skill_id, message: _cron_deliver_message(context, persona_id, skill_id, message)
            )
            context.cron_scheduler.register_skills(cron_skills, persona_ids=list(personas.keys()))
            context.cron_scheduler.start()

        proactive_config = _load_proactive_config(base_dir)
        context.proactive_service = ProactiveService(
            state_store=state_store,
            session_manager=context.session_manager,
            evermemos=evermemos,
            ws_connections=context.ws_registry.session_connections,
            persist_agent=lambda agent: _persist_agent(context, agent),
            instance_id=INSTANCE_ID,
            config=proactive_config,
            interval_seconds=PROACTIVE_INTERVAL_SECONDS,
        )
        context.proactive_task = asyncio.create_task(context.proactive_service.heartbeat_loop())
        print(f"✓ 主动消息心跳已启动 (cooldown={proactive_config['cooldown_hours']}h, ttl={proactive_config['lock_ttl']}s)")
    else:
        if cron_skills:
            print("⚠ LLM 未配置，已跳过定时任务调度")
        context.proactive_service = None
        context.proactive_task = None

    print("✓ OpenHer 服务启动完成 (v0.5.0 — Genome v10 Hybrid Engine)")


async def shutdown(context: AppContext) -> None:
    """Persist runtime state and close resources on server shutdown."""
    if context.proactive_task and not context.proactive_task.done():
        context.proactive_task.cancel()
        try:
            await context.proactive_task
        except asyncio.CancelledError:
            pass
        context.proactive_task = None

    if context.cron_scheduler:
        context.cron_scheduler.stop()
    if context.state_store:
        if context.session_manager:
            context.session_manager.persist_all()
        context.state_store.close()
    if context.memory_store:
        context.memory_store.close()
    if context.chat_log_store:
        context.chat_log_store.close()
    if context.evermemos and context.evermemos.available and context.session_manager:
        tasks = [
            context.evermemos.close_session(
                user_id=agent.evermemos_uid,
                persona_id=agent.persona.persona_id,
                group_id=agent._group_id,
            )
            for agent in context.session_manager.active_agents()
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    print("✓ 状态已保存，服务关闭")


def sync_legacy_globals(context: AppContext, module_globals: dict[str, object]) -> None:
    """Expose context services through legacy `main.py` global names."""
    module_globals.update(
        {
            "persona_loader": context.persona_loader,
            "llm_client": context.llm_client,
            "tts_engine": context.tts_engine,
            "task_skill_engine": context.task_skill_engine,
            "modality_skill_engine": context.modality_skill_engine,
            "state_store": context.state_store,
            "chat_log_store": context.chat_log_store,
            "memory_store": context.memory_store,
            "evermemos": context.evermemos,
            "cron_scheduler": context.cron_scheduler,
            "session_agent_factory": context.session_agent_factory,
            "session_manager": context.session_manager,
            "chat_api_service": context.chat_api_service,
            "media_api_service": context.media_api_service,
            "persona_api_service": context.persona_api_service,
            "proactive_service": context.proactive_service,
            "ws_demo_command_service": context.ws_demo_command_service,
            "ws_route_service": context.ws_route_service,
            "ws_chat_turn_service": context.ws_chat_turn_service,
            "persona_switch_service": context.persona_switch_service,
            "ws_tts_service": context.ws_tts_service,
            "genome_data_dir": context.genome_data_dir,
            "_proactive_task": context.proactive_task,
        }
    )
