"""Backend live-process runtime smoke command tests."""

from __future__ import annotations

import importlib.util
import socket
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "integration" / "backend_runtime_smoke.py"


def load_runtime_smoke_module():
    assert SCRIPT.exists(), "backend runtime smoke script must exist"
    spec = importlib.util.spec_from_file_location("backend_runtime_smoke", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backend_runtime_smoke_exposes_live_process_checks():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "subprocess.Popen" in source
    assert "-m" in source
    assert "uvicorn" in source
    assert "main:app" in source
    assert "def find_free_port()" in source
    assert "def start_server" in source
    assert "def wait_for_status" in source
    assert "def stop_server" in source
    assert "def check_live_personas" in source
    assert "def check_live_history" in source
    assert "OPENHER_API_TOKEN" in source
    assert "redact_known_secrets" in source


def test_find_free_port_returns_bindable_local_port():
    smoke = load_runtime_smoke_module()

    port = smoke.find_free_port()

    assert isinstance(port, int)
    assert port > 0
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))


def test_stop_server_terminates_child_process():
    smoke = load_runtime_smoke_module()
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        cwd=ROOT,
    )

    smoke.stop_server(process)

    assert process.poll() is not None
