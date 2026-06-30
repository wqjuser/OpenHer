"""Repository quality gate configuration tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_ci_workflow() -> dict[str, Any]:
    workflow_path = ROOT / ".github" / "workflows" / "ci.yml"
    assert workflow_path.exists(), "CI workflow must exist at .github/workflows/ci.yml"
    return yaml.load(workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def all_ci_run_blocks(workflow: dict[str, Any]) -> str:
    run_blocks: list[str] = []
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if "run" in step:
                run_blocks.append(step["run"])
    return "\n".join(run_blocks)


def test_ci_workflow_runs_on_push_pull_request_and_manual_dispatch():
    workflow = load_ci_workflow()

    triggers = workflow["on"]

    assert "pull_request" in triggers
    assert "workflow_dispatch" in triggers
    assert triggers["push"]["branches"] == ["main"]


def test_ci_workflow_has_backend_and_desktop_jobs():
    workflow = load_ci_workflow()

    jobs = workflow["jobs"]

    assert "backend" in jobs
    assert jobs["backend"]["strategy"]["matrix"]["python-version"] == ["3.11", "3.13"]
    assert "desktop" in jobs
    assert jobs["desktop"]["runs-on"] == "macos-latest"


def test_ci_workflow_runs_backend_quality_commands():
    workflow = load_ci_workflow()
    run_blocks = all_ci_run_blocks(workflow)

    assert "pip install -r requirements-dev.txt" in run_blocks
    assert "python -m pyright" in run_blocks
    assert "python -m pytest tests/ -q" in run_blocks
    assert "python -m py_compile main.py wechat_adapter.py" in run_blocks
    assert "python -m compileall agent engine memory persona providers server skills tests main.py wechat_adapter.py" in run_blocks
    assert "git diff --check" in run_blocks


def test_ci_workflow_builds_desktop_swift_package():
    workflow = load_ci_workflow()
    run_blocks = all_ci_run_blocks(workflow)

    assert "swift build" in run_blocks


def test_dev_requirements_include_runtime_requirements_and_tooling():
    requirements_path = ROOT / "requirements-dev.txt"
    assert requirements_path.exists(), "requirements-dev.txt must exist"

    text = requirements_path.read_text(encoding="utf-8")

    assert "-r requirements.txt" in text
    assert "pyright==" in text
    assert "ruff==" in text


def test_makefile_exposes_local_quality_gate_targets():
    makefile_path = ROOT / "Makefile"
    assert makefile_path.exists(), "Makefile must exist"

    text = makefile_path.read_text(encoding="utf-8")

    for target in (
        "install",
        "test",
        "typecheck",
        "compile",
        "check",
        "integration-smoke",
        "backend-acceptance-smoke",
        "backend-runtime-smoke",
        "backend-websocket-smoke",
        "backend-chat-smoke",
        "desktop-build",
    ):
        assert f"{target}:" in text

    assert "PYTHON ?= .venv/bin/python" in text
    assert "$(PYTHON) -m pytest tests/ -q" in text
    assert "$(PYTHON) -m pyright" in text
    assert "$(PYTHON) -m compileall agent engine memory persona providers server skills tests main.py wechat_adapter.py" in text
    assert "swift build" in text
    assert "$(PYTHON) -m py_compile scripts/integration/backend_acceptance_smoke.py" in text
    assert "$(PYTHON) scripts/integration/backend_acceptance_smoke.py" in text
    assert "$(PYTHON) -m py_compile scripts/integration/backend_runtime_smoke.py" in text
    assert "$(PYTHON) scripts/integration/backend_runtime_smoke.py" in text
    assert "$(PYTHON) -m py_compile scripts/integration/backend_websocket_smoke.py" in text
    assert "$(PYTHON) scripts/integration/backend_websocket_smoke.py" in text
    assert "$(PYTHON) -m py_compile scripts/integration/backend_chat_smoke.py" in text
    assert "$(PYTHON) scripts/integration/backend_chat_smoke.py" in text
