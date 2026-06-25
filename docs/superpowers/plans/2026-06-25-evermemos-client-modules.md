# EverMemOS Client Modules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split EverMemOS support concerns out of `evermemos_client.py` while preserving the current public and test-visible import surface.

**Architecture:** Keep `EverMemOSClient` focused on HTTP request orchestration. Move configuration loading, latency formatting, the session context DTO, and circuit breaker implementations into small sibling modules under `providers/memory/evermemos/`. Re-export the existing private names from `evermemos_client.py` by importing them there, so existing tests and callers continue to work.

**Tech Stack:** Python 3.11+, pytest, pyright, httpx optional import pattern.

---

### Task 1: Lock Module Boundaries With a Failing Test

**Files:**
- Create: `tests/test_evermemos_modules.py`

- [x] **Step 1: Write the failing test**

```python
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
    source = (ROOT / "providers/memory/evermemos/evermemos_client.py").read_text(encoding="utf-8")

    assert "from providers.memory.evermemos.config import _CFG, _fmt_latency, _load_memory_config" in source
    assert "from providers.memory.evermemos.types import SessionContext" in source
    assert "from providers.memory.evermemos.circuit_breaker import _CircuitBreaker, _NoOpBreaker" in source
    assert "class SessionContext" not in source
    assert "class _CircuitBreaker" not in source
    assert "def _load_memory_config" not in source
```

- [x] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_evermemos_modules.py -q`

Expected: FAIL because `providers.memory.evermemos.config` does not exist yet.

### Task 2: Extract Config and Latency Formatting

**Files:**
- Create: `providers/memory/evermemos/config.py`
- Modify: `providers/memory/evermemos/evermemos_client.py`
- Test: `tests/test_evermemos_modules.py`

- [x] **Step 1: Add `config.py`**

Create `providers/memory/evermemos/config.py` with `_load_memory_config`, `_CFG`, and `_fmt_latency` moved from `evermemos_client.py`. Keep the config path as `Path(__file__).parent / "memory_config.yaml"` so the sibling YAML file is still discovered.

- [x] **Step 2: Update `evermemos_client.py` imports**

Add:

```python
from providers.memory.evermemos.config import _CFG, _fmt_latency, _load_memory_config
```

Remove the inline `_load_memory_config`, `_CFG`, and `_fmt_latency` definitions from `evermemos_client.py`.

- [x] **Step 3: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_evermemos_modules.py tests/test_security_regressions.py::EverMemOSLoggingRegressionTests -q`

Expected: module boundary test still fails until Task 3 extracts types and circuit breaker; existing EverMemOS regression tests pass or expose import issues to fix in this task.

### Task 3: Extract Session Context and Circuit Breaker

**Files:**
- Create: `providers/memory/evermemos/types.py`
- Create: `providers/memory/evermemos/circuit_breaker.py`
- Modify: `providers/memory/evermemos/evermemos_client.py`
- Test: `tests/test_evermemos_modules.py`

- [x] **Step 1: Add `types.py`**

Create `providers/memory/evermemos/types.py` with the existing `SessionContext` dataclass and its fields unchanged.

- [x] **Step 2: Add `circuit_breaker.py`**

Create `providers/memory/evermemos/circuit_breaker.py` with the existing `_CircuitBreaker` and `_NoOpBreaker` classes unchanged.

- [x] **Step 3: Update `evermemos_client.py` imports**

Add:

```python
from providers.memory.evermemos.circuit_breaker import _CircuitBreaker, _NoOpBreaker
from providers.memory.evermemos.types import SessionContext
```

Remove the inline `SessionContext`, `_CircuitBreaker`, and `_NoOpBreaker` definitions. Remove imports that are no longer used after the extraction.

- [x] **Step 4: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_evermemos_modules.py tests/test_security_regressions.py::EverMemOSLoggingRegressionTests -q`

Expected: all selected tests pass.

### Task 4: Type Check and Full Regression

**Files:**
- Verify: `providers/memory/evermemos/config.py`
- Verify: `providers/memory/evermemos/types.py`
- Verify: `providers/memory/evermemos/circuit_breaker.py`
- Verify: `providers/memory/evermemos/evermemos_client.py`
- Verify: `tests/test_evermemos_modules.py`

- [x] **Step 1: Run static checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

- [x] **Step 2: Run compile check**

Run: `.venv/bin/python -m py_compile providers/memory/evermemos/config.py providers/memory/evermemos/types.py providers/memory/evermemos/circuit_breaker.py providers/memory/evermemos/evermemos_client.py`

Expected: exit code 0.

- [x] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest tests/ -v`

Expected: full test suite passes with the known skipped test count unchanged.

- [x] **Step 4: Run repository hygiene checks**

Run: `.venv/bin/python -m compileall agent engine memory persona providers server skills tests main.py wechat_adapter.py`

Expected: exit code 0.

Run: `git diff --check`

Expected: exit code 0.

### Self-Review

- Spec coverage: The plan extracts each support concern named in the goal and preserves `evermemos_client.py` compatibility through imports.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: Module names and imported symbols match the test expectations and the existing class/function names.
