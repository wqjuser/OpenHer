"""Contract tests for the optional live-provider smoke profile."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


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

    assert "integration-smoke:" in makefile
    assert "RUN_OPENHER_INTEGRATION=1" in makefile
    assert "scripts/integration/provider_smoke.py" in makefile
    assert "make integration-smoke" in readme
    assert "RUN_OPENHER_INTEGRATION=1" in readme
    assert "TTS/Image provider factory smoke" in readme
    assert "不会生成音频或图片" in readme
