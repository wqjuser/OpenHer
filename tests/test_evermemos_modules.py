from pathlib import Path
import importlib


ROOT = Path(__file__).resolve().parents[1]


def test_evermemos_support_modules_export_boundaries():
    config = importlib.import_module("providers.memory.evermemos.config")
    types = importlib.import_module("providers.memory.evermemos.types")
    circuit = importlib.import_module("providers.memory.evermemos.circuit_breaker")

    assert hasattr(config, "_load_memory_config")
    assert hasattr(config, "_CFG")
    assert hasattr(config, "_fmt_latency")
    assert hasattr(types, "SessionContext")
    assert hasattr(circuit, "_CircuitBreaker")
    assert hasattr(circuit, "_NoOpBreaker")


def test_evermemos_client_delegates_support_boundaries_to_modules():
    source = (ROOT / "providers/memory/evermemos/evermemos_client.py").read_text(
        encoding="utf-8"
    )

    assert (
        "from providers.memory.evermemos.config import _CFG, _fmt_latency, "
        "_load_memory_config"
    ) in source
    assert "from providers.memory.evermemos.types import SessionContext" in source
    assert (
        "from providers.memory.evermemos.circuit_breaker import "
        "_CircuitBreaker, _NoOpBreaker"
    ) in source
    assert "class SessionContext" not in source
    assert "class _CircuitBreaker" not in source
    assert "def _load_memory_config" not in source
