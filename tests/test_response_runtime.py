from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import importlib
import importlib.util
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


class FakeGenomeAgent:
    def __init__(self):
        self.step_calls: list[tuple[dict[str, Any], float, dict[str, float]]] = []

    def step(
        self,
        context: dict[str, Any],
        reward: float,
        drive_satisfaction: dict[str, float],
    ) -> None:
        self.step_calls.append((context, reward, drive_satisfaction))


def make_agent():
    spec = importlib.util.find_spec("agent.response_runtime")
    assert spec is not None
    module = importlib.import_module("agent.response_runtime")

    class DummyAgent(module.AgentResponseRuntimeMixin):
        def __init__(self):
            self.agent = FakeGenomeAgent()
            self._last_drive_satisfaction: dict[str, float] = {}
            self.modality_calls: list[dict[str, Any]] = []
            self.finalize_calls: list[dict[str, Any]] = []

        async def _execute_modality_skills(
            self,
            raw_text: str,
            reply: str,
            modality: str,
        ):
            self.modality_calls.append(
                {
                    "raw_text": raw_text,
                    "reply": reply,
                    "modality": modality,
                }
            )
            return SimpleNamespace(
                reply=f"{reply}!",
                modality=f"{modality}-skill",
                outputs={"image_path": "/tmp/generated.png"},
            )

        def _finalize_turn_response(
            self,
            user_message: str,
            reply: str,
            monologue: str,
            modality: str,
            context: dict[str, Any],
            drive_satisfaction: dict[str, float],
            reward: float,
            *,
            is_proactive: bool = False,
        ) -> None:
            self.finalize_calls.append(
                {
                    "user_message": user_message,
                    "reply": reply,
                    "monologue": monologue,
                    "modality": modality,
                    "context": context,
                    "drive_satisfaction": drive_satisfaction,
                    "reward": reward,
                    "is_proactive": is_proactive,
                }
            )

    return DummyAgent(), module


async def test_response_runtime_completes_actor_response_and_clamps_reward():
    agent, _module = make_agent()
    raw_text = "【内心独白】thinking\n【最终回复】hi\n【表达方式】文字"
    context = {"entropy": 0.8}
    drive_satisfaction = {"connection": 0.6}

    completed = await agent._complete_actor_response(
        user_message="hello",
        raw_text=raw_text,
        context=context,
        drive_satisfaction=drive_satisfaction,
        reward=2.0,
    )

    assert agent.modality_calls == [
        {
            "raw_text": raw_text,
            "reply": "hi",
            "modality": "文字",
        }
    ]
    assert agent.agent.step_calls == [(context, 1.0, drive_satisfaction)]
    assert agent._last_drive_satisfaction is drive_satisfaction
    assert agent.finalize_calls == [
        {
            "user_message": "hello",
            "reply": "hi!",
            "monologue": "thinking",
            "modality": "文字-skill",
            "context": context,
            "drive_satisfaction": drive_satisfaction,
            "reward": 2.0,
            "is_proactive": False,
        }
    ]
    assert completed.reply == "hi!"
    assert completed.modality == "文字-skill"
    assert completed.monologue == "thinking"
    assert completed.outputs == {"image_path": "/tmp/generated.png"}


async def test_response_runtime_preserves_proactive_turn_flag():
    agent, _module = make_agent()

    await agent._complete_actor_response(
        user_message="check in",
        raw_text="【内心独白】soft\n【最终回复】thinking of you\n【表达方式】文字",
        context={"entropy": 0.2},
        drive_satisfaction={},
        reward=-2.0,
        is_proactive=True,
    )

    assert agent.agent.step_calls == [({"entropy": 0.2}, -1.0, {})]
    assert agent.finalize_calls[0]["is_proactive"] is True


def test_completed_actor_response_dataclass_exports_expected_fields():
    _agent, module = make_agent()

    completed = module.CompletedActorResponse(
        reply="hello",
        modality="文字",
        monologue="thinking",
        outputs={"audio_path": "/tmp/a.wav"},
    )

    assert completed.reply == "hello"
    assert completed.modality == "文字"
    assert completed.monologue == "thinking"
    assert completed.outputs == {"audio_path": "/tmp/a.wav"}


def test_chat_agent_delegates_response_runtime_boundary():
    source = (ROOT / "agent/chat_agent.py").read_text(encoding="utf-8")

    assert "from agent.response_runtime import AgentResponseRuntimeMixin" in source
    assert "AgentResponseRuntimeMixin" in source
    assert source.count("_complete_actor_response(") == 2
    assert "extract_reply(" not in source
    assert "await self._execute_modality_skills(" not in source
    assert "self.agent.step(" not in source
    assert "self._last_drive_satisfaction = drive_satisfaction" not in source
    assert "self._finalize_turn_response(" not in source
