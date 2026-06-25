import asyncio
import importlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


class SkillResult:
    def __init__(self, success, output=None):
        self.success = success
        self.output = output or {}


class CapturingEngine:
    def __init__(self, results):
        self.results = results
        self.calls = []

    async def plan_and_execute(self, **kwargs):
        self.calls.append(kwargs)
        return self.results


def make_dummy_agent(engine):
    spec = importlib.util.find_spec("agent.modality_execution")
    assert spec is not None
    module = importlib.import_module("agent.modality_execution")

    class DummyAgent(module.ModalityExecutionMixin):
        def __init__(self, engine):
            self.modality_skill_engine = engine
            self.persona = SimpleNamespace(persona_id="luna")
            self.llm = object()
            self.history = []
            self._skill_outputs = {"stale": "value"}
            self._pending_retry = {"old": True}
            self._fallback_history_added = False

        async def _modality_failure_with_retry(
            self,
            failed_modality,
            original_reply,
            express_content,
        ):
            self.retry_args = (failed_modality, original_reply, express_content)
            return "fallback reply"

    return DummyAgent(engine)


def test_modality_execution_uses_structured_skill_context():
    engine = CapturingEngine(
        [SkillResult(True, {"_modality": "照片", "image_path": "/tmp/a.png"})]
    )
    agent = make_dummy_agent(engine)
    raw_text = "【内心独白】想拍照\n【最终回复】看这里\n【表达方式】照片，参考头像"

    result = asyncio.run(agent._execute_modality_skills(raw_text, "看这里", "文字"))

    assert result.reply == "看这里"
    assert result.modality == "照片"
    assert result.outputs == {"_modality": "照片", "image_path": "/tmp/a.png"}
    assert agent._pending_retry is None
    call = engine.calls[0]
    assert call["raw_modality"] == "照片，参考头像"
    assert json.loads(call["raw_output"]) == {"reply": "看这里", "modality": "文字"}


def test_modality_execution_falls_back_to_text_when_all_skills_fail():
    engine = CapturingEngine([SkillResult(False), SkillResult(False)])
    agent = make_dummy_agent(engine)
    raw_text = "【内心独白】想说话\n【最终回复】听我说\n【表达方式】语音"

    result = asyncio.run(agent._execute_modality_skills(raw_text, "听我说", "语音"))

    assert result.reply == "fallback reply"
    assert result.modality == "文字"
    assert agent._fallback_history_added is True
    assert agent.retry_args == ("语音", "听我说", raw_text)


def test_chat_agent_delegates_modality_execution_boundary():
    source = (ROOT / "agent/chat_agent.py").read_text(encoding="utf-8")

    assert "from agent.modality_execution import ModalityExecutionMixin" in source
    assert "ModalityExecutionMixin" in source
    assert source.count("_execute_modality_skills(") == 2
    assert "plan_and_execute(" not in source
