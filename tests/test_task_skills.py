from pathlib import Path
from types import SimpleNamespace
import importlib
import importlib.util


ROOT = Path(__file__).resolve().parents[1]


class FakeTaskSkillEngine:
    def __init__(self, observations=None, error=None):
        self.observations = observations
        self.error = error
        self.calls = []

    async def react_loop(self, user_message, llm):
        self.calls.append((user_message, llm))
        if self.error:
            raise self.error
        return self.observations


class FakeTaskLogStore:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def log_execution(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error


def make_agent(task_skill_engine=None, task_log_store=None):
    spec = importlib.util.find_spec("agent.task_skills")
    assert spec is not None
    module = importlib.import_module("agent.task_skills")

    class DummyAgent(module.AgentTaskSkillMixin):
        def __init__(self):
            self.task_skill_engine = task_skill_engine
            self.llm = object()
            self.task_log_store = task_log_store
            self.persona = SimpleNamespace(persona_id="luna")

    return DummyAgent()


async def test_task_skill_mixin_injects_observations_into_user_message():
    engine = FakeTaskSkillEngine(observations="weather=21C")
    agent = make_agent(task_skill_engine=engine)

    result = await agent._run_task_skills("天气如何")

    assert "天气如何" in result
    assert "以下是真实查询数据" in result
    assert "weather=21C" in result
    assert engine.calls == [("天气如何", agent.llm)]


async def test_task_skill_mixin_preserves_message_without_engine_or_on_error():
    assert await make_agent()._run_task_skills("hello") == "hello"

    engine = FakeTaskSkillEngine(error=RuntimeError("boom"))
    agent = make_agent(task_skill_engine=engine)

    assert await agent._run_task_skills("hello") == "hello"
    assert engine.calls == [("hello", agent.llm)]


def test_task_skill_mixin_logs_execution_and_swallows_store_errors():
    store = FakeTaskLogStore()
    agent = make_agent(task_log_store=store)

    agent._log_task(
        "weather",
        "天气",
        {"command": "curl", "stdout": "sunny", "stderr": "", "success": True},
        "晴天",
    )

    assert store.calls == [
        {
            "persona_id": "luna",
            "skill_id": "weather",
            "user_input": "天气",
            "command": "curl",
            "stdout": "sunny",
            "stderr": "",
            "success": True,
            "reply": "晴天",
        }
    ]

    failing = make_agent(task_log_store=FakeTaskLogStore(error=RuntimeError("db")))
    failing._log_task("weather", "天气", {}, "fallback")


def test_chat_agent_delegates_task_skill_boundary():
    source = (ROOT / "agent/chat_agent.py").read_text(encoding="utf-8")

    assert "from agent.task_skills import AgentTaskSkillMixin" in source
    assert "AgentTaskSkillMixin" in source
    assert "def _run_task_skills(" not in source
    assert "def _log_task(" not in source
