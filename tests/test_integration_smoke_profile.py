"""Contract tests for the optional live-provider smoke profile."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "integration" / "provider_smoke.py"


def test_provider_smoke_script_is_explicitly_opt_in() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "RUN_OPENHER_INTEGRATION" in source
    assert "load_dotenv" in source
    assert "get_llm_config" in source
    assert "LLMClient" in source
    assert "ChatMessage" in source
    assert "get_memory_config" in source
    assert "EverMemOSClient" in source
    assert "get_tts_config" in source
    assert "get_image_config" in source
    assert "get_tts" in source
    assert "get_image_gen" in source
    assert "async def smoke_llm_chat" in source
    assert "async def smoke_evermemos" in source
    assert "async def smoke_tts_provider" in source
    assert "async def smoke_image_provider" in source
    assert "print(cfg" not in source
    assert "print(llm_cfg" not in source
    assert "print(memory_cfg" not in source
    assert "print(tts_cfg" not in source
    assert "print(image_cfg" not in source


def test_provider_smoke_script_skips_without_opt_in() -> None:
    env = os.environ.copy()
    env.pop("RUN_OPENHER_INTEGRATION", None)

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0
    assert "Integration smoke skipped" in result.stdout
    assert "API_KEY" not in result.stdout
    assert "api_key" not in result.stdout
    assert result.stderr == ""


def test_makefile_and_readme_document_integration_smoke() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "integration-smoke:" in makefile
    assert "RUN_OPENHER_INTEGRATION=1" in makefile
    assert "scripts/integration/provider_smoke.py" in makefile
    assert "make integration-smoke" in readme
    assert "make backend-acceptance-smoke" in readme
    assert "make backend-runtime-smoke" in readme
    assert "make backend-websocket-smoke" in readme
    assert "make backend-chat-smoke" in readme
    assert "RUN_OPENHER_INTEGRATION=1" in readme
    assert "真实 uvicorn" in readme
    assert "真实 WebSocket" in readme
    assert "真实 LLM" in readme
    assert "service_unavailable" in readme
    assert "聊天不可用时会跳过" in readme
    assert "默认测试和 `make check` 不会启动后端进程" in readme
    assert "TTS/Image provider factory smoke" in readme
    assert "不会生成音频或图片" in readme
    assert "TTS_API_KEY" in readme
    assert "IMAGE_API_KEY" in readme
    assert "TTS_API_KEY" in env_example
    assert "IMAGE_API_KEY" in env_example
    assert "MEMORY_API_KEY" in readme
    assert "MEMORY_BASE_URL" in readme
    assert "MEMORY_API_KEY" in env_example
    assert "MEMORY_BASE_URL" in env_example
    assert "OPENHER_DATA_DIR" in readme
    assert "OPENHER_DATA_DIR" in env_example


async def test_llm_smoke_skips_when_provider_is_unavailable() -> None:
    from scripts.integration import provider_smoke

    class ExplodingLLMClient:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("LLMClient should not be constructed for unavailable providers")

    unavailable_cfg = {
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "available": False,
        "missing_key_env": "DEEPSEEK_API_KEY or LLM_API_KEY",
    }

    with patch("providers.config.get_llm_config", return_value=unavailable_cfg):
        with patch("providers.llm.client.LLMClient", ExplodingLLMClient):
            result = await provider_smoke.smoke_llm_chat()

    assert result == {
        "status": "skipped",
        "provider": "deepseek",
        "reason": "DEEPSEEK_API_KEY or LLM_API_KEY",
    }
