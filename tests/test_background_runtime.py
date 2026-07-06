"""Background runtime assembly boundary tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class FakeScheduler:
    def __init__(self) -> None:
        self.generator: Any | None = None
        self.callback: Any | None = None
        self.registered: list[tuple[list[Any], list[str]]] = []
        self.started = False

    def set_message_generator(self, fn: Any) -> None:
        self.generator = fn

    def set_message_callback(self, fn: Any) -> None:
        self.callback = fn

    def register_skills(self, skills: list[Any], persona_ids: list[str]) -> None:
        self.registered.append((skills, persona_ids))

    def start(self) -> None:
        self.started = True


class FakeSessionManager:
    def __init__(self) -> None:
        self.persisted: list[Any] = []

    def persist_agent(self, agent: Any) -> None:
        self.persisted.append(agent)


class FakeProactiveService:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    async def heartbeat_loop(self) -> None:
        return None


def test_background_runtime_builds_available_cron_and_proactive_services(tmp_path):
    from server.background_runtime import build_background_runtime_services

    scheduler = FakeScheduler()
    session_manager = FakeSessionManager()
    state_store = object()
    evermemos = object()
    ws_connections: dict[str, set[Any]] = {}
    cron_skills = [object()]
    created_tasks: list[Any] = []
    proactive_services: list[FakeProactiveService] = []

    def proactive_service_factory(**kwargs: Any) -> FakeProactiveService:
        service = FakeProactiveService(**kwargs)
        proactive_services.append(service)
        return service

    def create_task(coro: Any) -> str:
        created_tasks.append(coro)
        coro.close()
        return "task-handle"

    runtime = build_background_runtime_services(
        base_dir=tmp_path,
        llm_client=object(),
        persona_loader=object(),
        memory_store=object(),
        session_manager=session_manager,
        cron_skills=cron_skills,
        persona_ids=["iris", "nova"],
        state_store=state_store,
        evermemos=evermemos,
        ws_connections=ws_connections,
        instance_id="instance-1",
        proactive_interval_seconds=99,
        proactive_config={"cooldown_hours": 2, "max_pending": 7, "lock_ttl": 30},
        cron_scheduler_factory=lambda: scheduler,
        proactive_service_factory=proactive_service_factory,
        create_task=create_task,
    )

    assert runtime.cron_scheduler is scheduler
    assert scheduler.generator is not None
    assert scheduler.callback is not None
    assert scheduler.registered == [(cron_skills, ["iris", "nova"])]
    assert scheduler.started is True
    assert runtime.proactive_service is proactive_services[0]
    assert runtime.proactive_task == "task-handle"
    assert len(created_tasks) == 1

    proactive_kwargs = proactive_services[0].kwargs
    assert proactive_kwargs["state_store"] is state_store
    assert proactive_kwargs["session_manager"] is session_manager
    assert proactive_kwargs["evermemos"] is evermemos
    assert proactive_kwargs["ws_connections"] is ws_connections
    assert proactive_kwargs["instance_id"] == "instance-1"
    assert proactive_kwargs["config"] == {"cooldown_hours": 2, "max_pending": 7, "lock_ttl": 30}
    assert proactive_kwargs["interval_seconds"] == 99
    proactive_kwargs["persist_agent"]("agent-1")
    assert session_manager.persisted == ["agent-1"]
    assert runtime.messages == ("✓ 主动消息心跳已启动 (cooldown=2h, ttl=30s)",)


def test_background_runtime_degrades_when_llm_is_unavailable(tmp_path):
    from server.background_runtime import build_background_runtime_services

    def forbidden_factory(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("factory should not be called when llm is unavailable")

    runtime = build_background_runtime_services(
        base_dir=tmp_path,
        llm_client=None,
        persona_loader=object(),
        memory_store=object(),
        session_manager=FakeSessionManager(),
        cron_skills=[object()],
        persona_ids=["iris"],
        state_store=object(),
        evermemos=None,
        ws_connections={},
        instance_id="instance-1",
        proactive_interval_seconds=99,
        cron_scheduler_factory=forbidden_factory,
        proactive_service_factory=forbidden_factory,
        create_task=forbidden_factory,
    )

    assert runtime.cron_scheduler is None
    assert runtime.proactive_service is None
    assert runtime.proactive_task is None
    assert runtime.messages == ("⚠ LLM 未配置，已跳过定时任务调度",)


def test_load_proactive_config_uses_defaults_when_config_is_missing(tmp_path):
    from server.background_runtime import load_proactive_config

    assert load_proactive_config(tmp_path) == {
        "cooldown_hours": 4,
        "max_pending": 3,
        "lock_ttl": 600,
    }


def test_load_proactive_config_maps_yaml_overrides(tmp_path):
    from server.background_runtime import load_proactive_config

    config_path = Path(tmp_path) / "providers" / "memory" / "evermemos" / "memory_config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "evermemos:",
                "  proactive_cooldown_hours: 8",
                "  proactive_max_pending: 5",
                "  proactive_lock_ttl_sec: 120",
            ]
        ),
        encoding="utf-8",
    )

    assert load_proactive_config(tmp_path) == {
        "cooldown_hours": 8,
        "max_pending": 5,
        "lock_ttl": 120,
    }


async def test_generate_cron_message_uses_persona_name_and_skill_prompt():
    from server.background_runtime import generate_cron_message

    class FakePersona:
        name = "Iris"

    class FakePersonaLoader:
        def get(self, persona_id: str) -> FakePersona | None:
            assert persona_id == "iris"
            return FakePersona()

    class FakeResponse:
        content = "bring umbrella"

    class FakeLLM:
        def __init__(self) -> None:
            self.messages: list[Any] = []

        async def chat(self, messages: list[Any]) -> FakeResponse:
            self.messages = messages
            return FakeResponse()

    llm = FakeLLM()

    response = await generate_cron_message(
        persona_loader=FakePersonaLoader(),
        llm_client=llm,
        skill_prompt="提醒用户带伞",
        persona_id="iris",
    )

    assert response == "bring umbrella"
    assert llm.messages[0].role == "system"
    assert "Iris" in llm.messages[0].content
    assert "提醒用户带伞" in llm.messages[0].content
    assert llm.messages[1].role == "user"


async def test_deliver_cron_message_persists_broadcast_memory():
    from server.background_runtime import deliver_cron_message

    class FakeMemoryStore:
        def __init__(self) -> None:
            self.add_calls: list[dict[str, Any]] = []

        def add(self, **kwargs: Any) -> None:
            self.add_calls.append(kwargs)

    memory_store = FakeMemoryStore()

    await deliver_cron_message(
        memory_store=memory_store,
        persona_id="iris",
        skill_id="weather",
        message="bring umbrella",
    )

    assert memory_store.add_calls == [
        {
            "user_id": "__broadcast__",
            "persona_id": "iris",
            "content": "[weather] bring umbrella",
            "category": "event",
            "importance": 0.6,
        }
    ]
