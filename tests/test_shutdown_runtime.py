"""Shutdown runtime cleanup boundary tests."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import cast


class FakeTask:
    def __init__(self, events: list[str], *, done: bool = False) -> None:
        self.events = events
        self._done = done
        self.cancelled = False

    def done(self) -> bool:
        return self._done

    def cancel(self) -> None:
        self.cancelled = True
        self.events.append("task.cancel")

    def __await__(self):
        async def _await_cancel() -> None:
            self.events.append("task.await")
            raise asyncio.CancelledError

        return _await_cancel().__await__()


class FakeCronScheduler:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def stop(self) -> None:
        self.events.append("cron.stop")


class FakeStore:
    def __init__(self, events: list[str], name: str) -> None:
        self.events = events
        self.name = name

    def close(self) -> None:
        self.events.append(f"{self.name}.close")


class FakePersona:
    def __init__(self, persona_id: str) -> None:
        self.persona_id = persona_id


class FakeAgent:
    def __init__(self, user_id: str, persona_id: str, group_id: str) -> None:
        self.evermemos_uid = user_id
        self.persona = FakePersona(persona_id)
        self._group_id = group_id


class FakeSessionManager:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.agents = [
            FakeAgent("uid-1", "iris", "group-1"),
            FakeAgent("uid-2", "nova", "group-2"),
        ]

    def persist_all(self) -> None:
        self.events.append("session.persist_all")

    def active_agents(self) -> list[FakeAgent]:
        return self.agents


class FakeEverMemOS:
    available = True

    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def close_session(self, *, user_id: str, persona_id: str, group_id: str) -> None:
        self.events.append(f"evermemos.close:{user_id}:{persona_id}:{group_id}")


async def test_shutdown_runtime_cleans_resources_in_existing_order():
    from server.context import AppContext
    from server.shutdown_runtime import shutdown_runtime_services

    events: list[str] = []
    context = cast(
        AppContext,
        SimpleNamespace(
            proactive_task=FakeTask(events),
            cron_scheduler=FakeCronScheduler(events),
            session_manager=FakeSessionManager(events),
            state_store=FakeStore(events, "state"),
            memory_store=FakeStore(events, "memory"),
            chat_log_store=FakeStore(events, "chat"),
            evermemos=FakeEverMemOS(events),
        ),
    )

    messages = await shutdown_runtime_services(context)

    assert context.proactive_task is None
    assert events == [
        "task.cancel",
        "task.await",
        "cron.stop",
        "session.persist_all",
        "state.close",
        "memory.close",
        "chat.close",
        "evermemos.close:uid-1:iris:group-1",
        "evermemos.close:uid-2:nova:group-2",
    ]
    assert messages == ("✓ 状态已保存，服务关闭",)


async def test_shutdown_runtime_skips_missing_optional_dependencies():
    from server.context import AppContext
    from server.shutdown_runtime import shutdown_runtime_services

    events: list[str] = []
    completed_task = FakeTask(events, done=True)
    context = cast(
        AppContext,
        SimpleNamespace(
            proactive_task=completed_task,
            cron_scheduler=None,
            session_manager=None,
            state_store=None,
            memory_store=None,
            chat_log_store=None,
            evermemos=None,
        ),
    )

    messages = await shutdown_runtime_services(context)

    assert completed_task.cancelled is False
    assert context.proactive_task is completed_task
    assert events == []
    assert messages == ("✓ 状态已保存，服务关闭",)
