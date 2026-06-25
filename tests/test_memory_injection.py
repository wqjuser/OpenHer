import asyncio
import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def make_agent(lang="zh"):
    spec = importlib.util.find_spec("agent.memory_injection")
    assert spec is not None
    module = importlib.import_module("agent.memory_injection")

    class DummyAgent(module.MemoryInjectionMixin):
        def __init__(self):
            self._session_ctx = SimpleNamespace(has_history=True)
            self.persona = SimpleNamespace(lang=lang)
            self.user_name = "Codex"
            self._relevant_facts = "fresh facts"
            self._user_profile = "static profile"
            self._relevant_episodes = "fresh episodes"
            self._episode_summary = "static episode"
            self._foresight_text = "bring umbrella"
            self._relevant_profile = "likes concise answers"
            self._search_relevant_used = 0
            self.collect_calls = 0

        async def _collect_search_results(self):
            self.collect_calls += 1

        def _memory_injection_budget(self, context):
            return 100, 80

        def _blend_injection(self, relevant, static, budget):
            return f"{relevant}|{static}|{budget}"

    return DummyAgent()


def test_memory_injection_appends_chinese_sections_and_counts_relevant_use():
    agent = make_agent(lang="zh")

    prompt = asyncio.run(
        agent._inject_memory_context("BASE", {"conversation_depth": 0.5})
    )

    assert prompt.startswith("BASE")
    assert "[关于Codex的偏好] fresh facts|static profile|100" in prompt
    assert "[与Codex过去发生的事] fresh episodes|static episode|80" in prompt
    assert "[近期值得关心] bring umbrella" in prompt
    assert "[Codex的画像] likes concise answers" in prompt
    assert agent.collect_calls == 1
    assert agent._search_relevant_used == 1


def test_memory_injection_appends_english_sections():
    agent = make_agent(lang="en")

    prompt = asyncio.run(
        agent._inject_memory_context("BASE", {"conversation_depth": 0.5})
    )

    assert "[Codex's preferences] fresh facts|static profile|100" in prompt
    assert "[Past interactions with Codex] fresh episodes|static episode|80" in prompt
    assert "[Worth noting] bring umbrella" in prompt
    assert "[Codex's profile] likes concise answers" in prompt


def test_memory_injection_skips_when_session_has_no_history():
    agent = make_agent(lang="zh")
    agent._session_ctx = SimpleNamespace(has_history=False)

    prompt = asyncio.run(
        agent._inject_memory_context("BASE", {"conversation_depth": 0.5})
    )

    assert prompt == "BASE"
    assert agent.collect_calls == 0
    assert agent._search_relevant_used == 0


def test_chat_agent_delegates_memory_injection_boundary():
    source = (ROOT / "agent/chat_agent.py").read_text(encoding="utf-8")

    assert "from agent.memory_injection import MemoryInjectionMixin" in source
    assert "MemoryInjectionMixin" in source
    assert source.count("_inject_memory_context(") == 2
    assert "await self._collect_search_results()" not in source
    assert "[关于{name}的偏好]" not in source
    assert "[Past interactions with {name}]" not in source
