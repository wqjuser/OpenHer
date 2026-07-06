"""Background runtime service assembly for OpenHer startup."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Coroutine, Mapping

from agent.cron_scheduler import CronScheduler
from server.proactive_service import ProactiveService


ProactiveConfig = dict[str, Any]
CronSchedulerFactory = Callable[[], Any]
ProactiveServiceFactory = Callable[..., Any]
TaskCreator = Callable[[Coroutine[Any, Any, None]], Any]
ProactiveConfigLoader = Callable[[Path], ProactiveConfig]
CronMessageGenerator = Callable[[Any | None, Any | None, str, str], Coroutine[Any, Any, str]]
CronMessageDelivery = Callable[[Any | None, str, str, str], Coroutine[Any, Any, None]]


@dataclass(frozen=True)
class BackgroundRuntimeServices:
    cron_scheduler: CronScheduler | None
    proactive_service: ProactiveService | None
    proactive_task: Any | None
    messages: tuple[str, ...]


def load_proactive_config(base_dir: Path) -> ProactiveConfig:
    try:
        import yaml as yaml_cfg

        cfg_path = Path(base_dir) / "providers" / "memory" / "evermemos" / "memory_config.yaml"
        cfg_doc = yaml_cfg.safe_load(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
        cfg_raw = cfg_doc.get("evermemos", {}) if isinstance(cfg_doc, Mapping) else {}
    except Exception:
        cfg_raw = {}

    if not isinstance(cfg_raw, Mapping):
        cfg_raw = {}

    return {
        "cooldown_hours": cfg_raw.get("proactive_cooldown_hours", 4),
        "max_pending": cfg_raw.get("proactive_max_pending", 3),
        "lock_ttl": cfg_raw.get("proactive_lock_ttl_sec", 600),
    }


async def generate_cron_message(
    persona_loader: Any | None,
    llm_client: Any | None,
    skill_prompt: str,
    persona_id: str,
) -> str:
    if not persona_loader or not llm_client:
        return ""
    persona = persona_loader.get(persona_id)
    if not persona:
        return ""

    from providers.llm.client import ChatMessage

    messages = [
        ChatMessage(role="system", content=f"你是{persona.name}。{skill_prompt}"),
        ChatMessage(role="user", content="请生成一条主动消息"),
    ]
    response = await llm_client.chat(messages)
    return str(response.content or "")


async def deliver_cron_message(
    memory_store: Any | None,
    persona_id: str,
    skill_id: str,
    message: str,
) -> None:
    print(f"[cron] 📨 {persona_id}/{skill_id}: {message[:60]}...")
    if memory_store:
        memory_store.add(
            user_id="__broadcast__",
            persona_id=persona_id,
            content=f"[{skill_id}] {message}",
            category="event",
            importance=0.6,
        )


def build_background_runtime_services(
    *,
    base_dir: Path,
    llm_client: Any | None,
    persona_loader: Any | None,
    memory_store: Any | None,
    session_manager: Any | None,
    cron_skills: list[Any],
    persona_ids: list[str],
    state_store: Any,
    evermemos: Any | None,
    ws_connections: dict[str, set[Any]],
    instance_id: str,
    proactive_interval_seconds: int,
    proactive_config: Mapping[str, Any] | None = None,
    proactive_config_loader: ProactiveConfigLoader = load_proactive_config,
    cron_message_generator: CronMessageGenerator = generate_cron_message,
    cron_message_delivery: CronMessageDelivery = deliver_cron_message,
    cron_scheduler_factory: CronSchedulerFactory = CronScheduler,
    proactive_service_factory: ProactiveServiceFactory = ProactiveService,
    create_task: TaskCreator = asyncio.create_task,
) -> BackgroundRuntimeServices:
    cron_scheduler = None
    proactive_service = None
    proactive_task = None
    messages: list[str] = []

    if llm_client and session_manager:
        if cron_skills:
            cron_scheduler = cron_scheduler_factory()
            cron_scheduler.set_message_generator(
                lambda skill_prompt, persona_id: cron_message_generator(
                    persona_loader,
                    llm_client,
                    skill_prompt,
                    persona_id,
                )
            )
            cron_scheduler.set_message_callback(
                lambda persona_id, skill_id, message: cron_message_delivery(
                    memory_store,
                    persona_id,
                    skill_id,
                    message,
                )
            )
            cron_scheduler.register_skills(cron_skills, persona_ids=persona_ids)
            cron_scheduler.start()

        config = proactive_config_loader(Path(base_dir))
        if proactive_config:
            config = {**config, **dict(proactive_config)}
        proactive_service = proactive_service_factory(
            state_store=state_store,
            session_manager=session_manager,
            evermemos=evermemos,
            ws_connections=ws_connections,
            persist_agent=lambda agent: session_manager.persist_agent(agent),
            instance_id=instance_id,
            config=config,
            interval_seconds=proactive_interval_seconds,
        )
        proactive_task = create_task(proactive_service.heartbeat_loop())
        messages.append(f"✓ 主动消息心跳已启动 (cooldown={config['cooldown_hours']}h, ttl={config['lock_ttl']}s)")
    else:
        if cron_skills:
            messages.append("⚠ LLM 未配置，已跳过定时任务调度")

    return BackgroundRuntimeServices(
        cron_scheduler=cron_scheduler,
        proactive_service=proactive_service,
        proactive_task=proactive_task,
        messages=tuple(messages),
    )
