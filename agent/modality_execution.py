from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from agent.parser import _SECTION_RE


@dataclass
class ModalityExecutionResult:
    reply: str
    modality: str
    outputs: dict[str, Any] = field(default_factory=dict)


class _ModalityExecutionHost(Protocol):
    modality_skill_engine: Any
    persona: Any
    llm: Any
    history: list[Any]
    _skill_outputs: dict[str, Any]
    _pending_retry: Any
    _fallback_history_added: bool

    async def _modality_failure_with_retry(
        self,
        failed_modality: str,
        original_reply: str,
        express_content: str,
    ) -> str:
        ...


class ModalityExecutionMixin:
    async def _execute_modality_skills(
        self,
        raw_text: str,
        reply: str,
        modality: str,
    ) -> ModalityExecutionResult:
        host = cast(_ModalityExecutionHost, self)
        host._skill_outputs = {}
        host._pending_retry = None

        raw_modality = ""
        matches = list(_SECTION_RE.finditer(raw_text))
        if matches:
            raw_modality = raw_text[matches[-1].end():].strip()
            print(f"  [express] raw_modality='{raw_modality[:80]}'")

        if host.modality_skill_engine and raw_modality:
            structured_context = json.dumps(
                {"reply": reply, "modality": modality},
                ensure_ascii=False,
            )
            print(f"  [skill-context] 📦 {structured_context[:200]}")
            skill_results = await host.modality_skill_engine.plan_and_execute(
                raw_modality=raw_modality,
                raw_output=structured_context,
                persona=host.persona,
                llm=host.llm,
                chat_history=host.history,
            )
            for skill_result in skill_results:
                if skill_result.success:
                    host._skill_outputs.update(skill_result.output)

            if host._skill_outputs.get("_modality"):
                modality = host._skill_outputs["_modality"]

            if skill_results and all(not result.success for result in skill_results):
                print("  [skill] ⚠ All skills failed, triggering LLM fallback")
                fallback_reply = await host._modality_failure_with_retry(
                    modality,
                    reply,
                    raw_text,
                )
                if fallback_reply:
                    reply = fallback_reply
                modality = "文字"
                host._fallback_history_added = True

        return ModalityExecutionResult(
            reply=reply,
            modality=modality,
            outputs=dict(host._skill_outputs),
        )
