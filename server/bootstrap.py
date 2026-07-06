"""Runtime service assembly for the OpenHer FastAPI application."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from agent.chat_agent import ChatAgent
from persona import PersonaLoader
from server.background_runtime import build_background_runtime_services
from server.context import AppContext
from server.persistence_runtime import build_persistence_runtime_services
from server.persona_api_service import PersonaApiService
from server.provider_runtime import build_provider_runtime_services
from server.session_runtime import build_session_runtime_services
from server.shutdown_runtime import shutdown_runtime_services
from server.skill_runtime import build_skill_runtime_services


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

    skill_runtime = build_skill_runtime_services(
        base_dir,
        voice_tools_enabled=provider_runtime.tts_available,
    )
    context.task_skill_engine = skill_runtime.task_skill_engine
    context.modality_skill_engine = skill_runtime.modality_skill_engine
    task_skill_engine = skill_runtime.task_skill_engine
    modality_skill_engine = skill_runtime.modality_skill_engine
    cron_skills = skill_runtime.cron_skills
    for message in skill_runtime.messages:
        print(message)

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

    session_runtime = build_session_runtime_services(
        base_dir=base_dir,
        llm_client=context.llm_client,
        persona_loader=context.persona_loader,
        task_skill_engine=task_skill_engine,
        modality_skill_engine=modality_skill_engine,
        memory_store=memory_store,
        state_store=state_store,
        evermemos=evermemos,
        genome_data_dir=context.genome_data_dir,
        chat_log_store=chat_log_store,
        ws_registry=context.ws_registry,
        ws_tts_service=context.ws_tts_service,
        ws_demo_proactive_service=context.ws_demo_proactive_service,
        get_or_create_session=lambda session_id, persona_id, user_name=None, client_id=None: _get_or_create_session(
            context, session_id, persona_id, user_name, client_id
        ),
        remove_session=lambda session_id: _remove_session(context, session_id),
        session_ttl_seconds=SESSION_TTL_SECONDS,
    )
    context.session_agent_factory = session_runtime.session_agent_factory
    context.session_manager = session_runtime.session_manager
    context.chat_api_service = session_runtime.chat_api_service
    context.persona_switch_service = session_runtime.persona_switch_service
    context.ws_chat_turn_service = session_runtime.ws_chat_turn_service
    context.ws_demo_command_service = session_runtime.ws_demo_command_service
    context.ws_route_service = session_runtime.ws_route_service
    session_manager = session_runtime.session_manager

    background_runtime = build_background_runtime_services(
        base_dir=base_dir,
        llm_client=context.llm_client,
        persona_loader=context.persona_loader,
        memory_store=memory_store,
        session_manager=session_manager,
        cron_skills=cron_skills,
        persona_ids=list(personas.keys()),
        state_store=state_store,
        evermemos=evermemos,
        ws_connections=context.ws_registry.session_connections,
        instance_id=INSTANCE_ID,
        proactive_interval_seconds=PROACTIVE_INTERVAL_SECONDS,
    )
    context.cron_scheduler = background_runtime.cron_scheduler
    context.proactive_service = background_runtime.proactive_service
    context.proactive_task = background_runtime.proactive_task
    for message in background_runtime.messages:
        print(message)

    print("✓ OpenHer 服务启动完成 (v0.5.0 — Genome v10 Hybrid Engine)")


async def shutdown(context: AppContext) -> None:
    """Persist runtime state and close resources on server shutdown."""
    messages = await shutdown_runtime_services(context)
    for message in messages:
        print(message)


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
