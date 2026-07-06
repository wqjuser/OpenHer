"""Shutdown cleanup runtime for OpenHer lifespan."""

from __future__ import annotations

import asyncio
from typing import Any

from server.context import AppContext, SessionManagerService


async def cancel_proactive_task(context: AppContext) -> None:
    task = context.proactive_task
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        context.proactive_task = None


async def close_evermemos_sessions(evermemos: Any | None, session_manager: SessionManagerService | None) -> None:
    if not evermemos or not evermemos.available or not session_manager:
        return

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


async def shutdown_runtime_services(context: AppContext) -> tuple[str, ...]:
    await cancel_proactive_task(context)

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

    await close_evermemos_sessions(context.evermemos, context.session_manager)
    return ("✓ 状态已保存，服务关闭",)
