"""Backend acceptance smoke command tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/integration/backend_acceptance_smoke.py"


def load_smoke_module():
    assert SCRIPT_PATH.exists(), "backend acceptance smoke script must exist"
    spec = importlib.util.spec_from_file_location("backend_acceptance_smoke", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backend_acceptance_smoke_exposes_core_checks():
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "def build_client()" in source
    assert "def check_status" in source
    assert "def check_personas" in source
    assert "def check_chat_history_empty_state" in source
    assert "def check_chat_unavailable" in source
    assert "def main() -> int" in source
    assert "TestClient" in source
    assert "AppContext()" in source
    assert "create_app(context)" in source


def test_backend_acceptance_smoke_runs_in_process_core_flow():
    smoke = load_smoke_module()

    client = smoke.build_client()
    status = smoke.check_status(client)
    persona_id = smoke.check_personas(client)
    history = smoke.check_chat_history_empty_state(client, persona_id)
    unavailable = smoke.check_chat_unavailable(client, persona_id)

    assert status["status"] == "ok"
    assert status["chat_available"] in {"true", "false"}
    assert persona_id
    assert history == {"status": "ok", "messages": "0", "total": "0"}
    assert unavailable["status"] == "ok"
    assert unavailable["http_status"] == "503"
