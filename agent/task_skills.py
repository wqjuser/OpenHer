from __future__ import annotations

from typing import Any, Protocol, cast


class _TaskSkillPersona(Protocol):
    persona_id: str


class _TaskSkillLogStore(Protocol):
    def log_execution(self, **kwargs: Any) -> None:
        ...


class _TaskSkillEngine(Protocol):
    async def react_loop(self, user_message: str, llm: Any) -> str:
        ...


class _TaskSkillHost(Protocol):
    task_skill_engine: _TaskSkillEngine | None
    llm: Any
    task_log_store: _TaskSkillLogStore | None
    persona: _TaskSkillPersona


class AgentTaskSkillMixin:
    """Task skill pre-processing and isolated task log persistence."""

    async def _run_task_skills(self, user_message: str) -> str:
        """Step -1: Run task skill ReAct loop before persona engine."""
        host = cast(_TaskSkillHost, self)
        if not host.task_skill_engine:
            return user_message
        try:
            observations = await host.task_skill_engine.react_loop(user_message, host.llm)
            if observations:
                user_message = (
                    f"{user_message}\n\n"
                    f"[以下是真实查询数据，回复中必须自然融入关键数值，不要省略]\n"
                    f"{observations}"
                )
                print(
                    f"  [skill] ✅ 数据已注入 ({len(observations)} chars), 继续引擎处理"
                )
        except Exception as e:
            print(f"  [skill] ⚠ ReAct loop failed ({e}), fallback to persona engine")
        return user_message

    def _log_task(
        self,
        skill_id: str,
        user_input: str,
        output: dict[str, Any],
        reply: str,
    ) -> None:
        """Log task execution to task.db (isolated from persona memory)."""
        host = cast(_TaskSkillHost, self)
        if not host.task_log_store:
            return
        try:
            host.task_log_store.log_execution(
                persona_id=host.persona.persona_id,
                skill_id=skill_id,
                user_input=user_input,
                command=output.get("command", ""),
                stdout=output.get("stdout", ""),
                stderr=output.get("stderr", ""),
                success=output.get("success", False),
                reply=reply,
            )
        except Exception as e:
            print(f"  [task_log] save error: {e}")
