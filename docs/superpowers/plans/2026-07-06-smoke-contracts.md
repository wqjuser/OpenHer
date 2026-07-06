# Smoke Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Share common integration smoke helpers and `/api/status` diagnostics validation without changing smoke command output.

**Architecture:** Create `scripts/integration/smoke_contracts.py` with typed validation and formatting helpers. Refactor existing smoke scripts to import those helpers while leaving each script's flow-specific checks local.

**Tech Stack:** Python 3.11+, dataclasses, pytest, pyright, existing Makefile quality gates.

---

### Task 1: Add Shared Smoke Contract Tests

**Files:**
- Create: `tests/test_integration_smoke_contracts.py`
- Modify: `tests/test_quality_gates.py`
- Modify: `tests/test_backend_runtime_smoke.py`
- Modify: `tests/test_backend_acceptance_smoke.py`
- Modify: `tests/test_desktop_acceptance_smoke.py`
- Modify: `tests/test_backend_chat_smoke.py`
- Modify: `tests/test_backend_websocket_smoke.py`
- Modify: `tests/test_integration_smoke_profile.py`

- [x] **Step 1: Add helper behavior tests**

Create `tests/test_integration_smoke_contracts.py`:

```python
"""Shared integration smoke contract tests."""

from __future__ import annotations

import json


def valid_status_body() -> dict:
    return {
        "status": "running",
        "providers": {
            "llm": {"provider": "deepseek", "available": True, "missing_key_env": "", "setup_hint": ""},
            "tts": {"provider": "dashscope", "available": False, "missing_key_env": "TTS_API_KEY", "setup_hint": "set tts"},
            "image": {"provider": "gemini", "available": True, "missing_key_env": "", "setup_hint": ""},
            "memory": {
                "provider": "evermemos",
                "enabled": True,
                "configured": True,
                "available": False,
                "setup_hint": "set memory",
            },
        },
        "capabilities": {
            "chat": {"available": True, "reason": "", "requires": ["llm"], "setup_hint": ""},
            "voice": {"available": False, "reason": "TTS missing", "requires": ["tts"], "setup_hint": "set tts"},
            "image": {"available": True, "reason": "", "requires": ["image"], "setup_hint": ""},
            "memory": {"available": False, "reason": "EverMemOS unavailable", "requires": ["memory"], "setup_hint": "set memory"},
        },
    }


def test_smoke_contracts_format_and_safe_value_helpers():
    from scripts.integration.smoke_contracts import format_result, safe_value

    assert format_result("status", {"z": "last", "a": "first"}) == "status: a=first z=last"
    assert safe_value("a\nb") == "a b"
    assert len(safe_value("x" * 600)) == 500


def test_smoke_contracts_decodes_json_objects_only():
    from scripts.integration.smoke_contracts import decode_json

    assert decode_json(json.dumps({"ok": True})) == {"ok": True}
    assert decode_json("") == {}
    try:
        decode_json(json.dumps(["not", "object"]))
    except AssertionError as exc:
        assert "expected JSON object" in str(exc)
    else:
        raise AssertionError("list JSON should fail")


def test_smoke_contracts_validates_status_diagnostics():
    from scripts.integration.smoke_contracts import bool_text, validate_status_diagnostics

    diagnostics = validate_status_diagnostics(valid_status_body(), require_setup_hints=True)

    assert diagnostics.chat["available"] is True
    assert diagnostics.voice["available"] is False
    assert diagnostics.memory_provider["configured"] is True
    assert bool_text(diagnostics.memory["available"], "memory available") == "false"


def test_smoke_contracts_rejects_missing_capability():
    from scripts.integration.smoke_contracts import validate_status_diagnostics

    body = valid_status_body()
    body["capabilities"].pop("memory")

    try:
        validate_status_diagnostics(body)
    except AssertionError as exc:
        assert "status.capabilities: missing memory" in str(exc)
    else:
        raise AssertionError("missing memory capability should fail")
```

- [x] **Step 2: Add source boundary tests**

Extend smoke source tests:

```python
assert "smoke_contracts" in source
assert "def _format_result" not in source
assert "def _safe_value" not in source
```

For scripts that currently define local object/status helpers, also assert:

```python
assert "def _require_dict" not in source
assert "def _require_status" not in source
```

Extend `test_backend_chat_smoke_exposes_live_chat_checks()`:

```python
assert "backend_runtime_smoke._require_status" not in source
assert "backend_runtime_smoke._decode_json" not in source
assert "backend_runtime_smoke._auth_headers" not in source
```

Extend `test_makefile_exposes_local_quality_gate_targets()`:

```python
assert "$(PYTHON) -m py_compile scripts/integration/smoke_contracts.py" in text
```

- [x] **Step 3: Run tests to verify red**

Run:

```bash
.venv/bin/python -m pytest tests/test_integration_smoke_contracts.py tests/test_backend_runtime_smoke.py::test_backend_runtime_smoke_exposes_live_process_checks tests/test_backend_acceptance_smoke.py::test_backend_acceptance_smoke_exposes_core_checks tests/test_desktop_acceptance_smoke.py::test_desktop_acceptance_smoke_exposes_startup_and_chat_flow_checks tests/test_backend_chat_smoke.py::test_backend_chat_smoke_exposes_live_chat_checks tests/test_backend_websocket_smoke.py::test_backend_websocket_smoke_exposes_live_ws_checks tests/test_integration_smoke_profile.py::test_provider_smoke_script_is_explicitly_opt_in tests/test_quality_gates.py::test_makefile_exposes_local_quality_gate_targets -v
```

Expected: FAIL because `smoke_contracts.py` does not exist and smoke scripts still define duplicate local helpers.

### Task 2: Implement Shared Smoke Contracts

**Files:**
- Create: `scripts/integration/smoke_contracts.py`
- Modify: `scripts/integration/backend_runtime_smoke.py`
- Modify: `scripts/integration/backend_acceptance_smoke.py`
- Modify: `scripts/integration/backend_chat_smoke.py`
- Modify: `scripts/integration/backend_websocket_smoke.py`
- Modify: `scripts/integration/desktop_acceptance_smoke.py`
- Modify: `scripts/integration/provider_smoke.py`
- Modify: `Makefile`

- [x] **Step 1: Add smoke helper module**

Create `scripts/integration/smoke_contracts.py` with:

```python
"""Shared helpers for OpenHer integration smoke contracts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


PROVIDER_KEYS = ("llm", "tts", "image", "memory")
CAPABILITY_KEYS = ("chat", "voice", "image", "memory")


@dataclass(frozen=True)
class StatusDiagnostics:
    providers: dict[str, Any]
    capabilities: dict[str, Any]
    chat: dict[str, Any]
    voice: dict[str, Any]
    image: dict[str, Any]
    memory: dict[str, Any]
    memory_provider: dict[str, Any]


def auth_headers(token: str) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def decode_json(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object, got {safe_value(value)}")
    return value


def require_status(status_code: int, expected: int, label: str, detail: Any = "") -> None:
    if status_code == expected:
        return
    suffix = f": {safe_value(detail)}" if detail else ""
    raise AssertionError(f"{label}: expected HTTP {expected}, got {status_code}{suffix}")


def require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AssertionError(f"{label}: expected object, got {safe_value(value)}")
    return value


def bool_text(value: Any, label: str) -> str:
    if not isinstance(value, bool):
        raise AssertionError(f"{label} must be a boolean")
    return str(value).lower()


def safe_value(value: Any) -> str:
    return str(value).replace("\n", " ")[:500]


def format_result(name: str, result: dict[str, str]) -> str:
    fields = " ".join(f"{key}={value}" for key, value in sorted(result.items()))
    return f"{name}: {fields}"


def validate_status_diagnostics(
    body: dict[str, Any],
    *,
    require_setup_hints: bool = False,
) -> StatusDiagnostics:
    if body.get("status") != "running":
        raise AssertionError(f"status: expected running, got {body.get('status')!r}")

    providers = require_dict(body.get("providers"), "status.providers")
    capabilities = require_dict(body.get("capabilities"), "status.capabilities")
    provider_sections = {key: require_dict(providers.get(key), f"status.providers.{key}") for key in PROVIDER_KEYS}
    capability_sections = {
        key: require_dict(capabilities.get(key), f"status.capabilities.{key}") for key in CAPABILITY_KEYS
    }

    for key in PROVIDER_KEYS:
        if key not in providers:
            raise AssertionError(f"status.providers: missing {key}")
        if require_setup_hints and not isinstance(provider_sections[key].get("setup_hint"), str):
            raise AssertionError(f"status.providers.{key}.setup_hint must be a string")

    for key in CAPABILITY_KEYS:
        if key not in capabilities:
            raise AssertionError(f"status.capabilities: missing {key}")
        section = capability_sections[key]
        if not isinstance(section.get("available"), bool):
            raise AssertionError(f"status.capabilities.{key}.available must be a boolean")
        if "reason" not in section:
            raise AssertionError(f"status.capabilities.{key}.reason is required")
        if require_setup_hints and not isinstance(section.get("setup_hint"), str):
            raise AssertionError(f"status.capabilities.{key}.setup_hint must be a string")

    memory_provider = provider_sections["memory"]
    for key in ("enabled", "configured", "available"):
        if not isinstance(memory_provider.get(key), bool):
            raise AssertionError(f"status.providers.memory.{key} must be a boolean")

    return StatusDiagnostics(
        providers=providers,
        capabilities=capabilities,
        chat=capability_sections["chat"],
        voice=capability_sections["voice"],
        image=capability_sections["image"],
        memory=capability_sections["memory"],
        memory_provider=memory_provider,
    )
```

- [x] **Step 2: Refactor runtime smoke**

Import:

```python
from scripts.integration.smoke_contracts import (
    auth_headers,
    decode_json,
    format_result,
    require_dict,
    require_status,
    safe_value,
    validate_status_diagnostics,
)
```

Use shared helpers in `request_json()`, `wait_for_status()`, `check_live_status()`, `check_live_personas()`, `check_live_history()`, and `main()`. Remove local `_auth_headers`, `_decode_json`, `_require_status`, `_require_dict`, `_format_result`, and `_safe_value`.

- [x] **Step 3: Refactor backend acceptance smoke**

Import:

```python
from scripts.integration.smoke_contracts import (
    format_result,
    require_dict,
    require_status,
    safe_value,
    validate_status_diagnostics,
)
```

Use `validate_status_diagnostics()` in `check_status()`, `require_status(response.status_code, ..., response.text)` for HTTP assertions, and shared formatting/safe helpers. Remove local duplicate helper definitions.

- [x] **Step 4: Refactor backend chat smoke**

Import:

```python
from scripts.integration.smoke_contracts import auth_headers, decode_json, format_result, require_status, safe_value
```

Use those helpers and remove local `_format_result()` / `_safe_value()`. Stop calling private helpers on `backend_runtime_smoke`.

- [x] **Step 5: Refactor backend WebSocket smoke**

Import:

```python
from scripts.integration.smoke_contracts import format_result, safe_value
```

Use shared helpers and remove local duplicates.

- [x] **Step 6: Refactor desktop acceptance smoke**

Import:

```python
from scripts.integration.smoke_contracts import (
    bool_text,
    format_result,
    require_dict,
    require_status,
    safe_value,
    validate_status_diagnostics,
)
```

Use `validate_status_diagnostics(..., require_setup_hints=True)` in `check_desktop_status_body()`, shared `require_status()` for HTTP assertions, and shared formatting/safe helpers. Remove local duplicate helpers.

- [x] **Step 7: Refactor provider smoke**

Import:

```python
from scripts.integration.smoke_contracts import format_result
```

Use shared `format_result()` and remove local `_format_result()`.

- [x] **Step 8: Add compile coverage**

Add this line to `Makefile` under `compile`:

```make
	$(PYTHON) -m py_compile scripts/integration/smoke_contracts.py
```

- [x] **Step 9: Run focused smoke tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_integration_smoke_contracts.py tests/test_backend_acceptance_smoke.py tests/test_backend_runtime_smoke.py tests/test_backend_websocket_smoke.py tests/test_backend_chat_smoke.py tests/test_desktop_acceptance_smoke.py tests/test_integration_smoke_profile.py tests/test_quality_gates.py -v
```

Expected: PASS.

### Task 3: Verify The Phase

**Files:**
- Modify: `docs/superpowers/plans/2026-07-06-smoke-contracts.md`

- [x] **Step 1: Mark completed plan checkboxes**

Update this plan so every executed step is checked.

- [x] **Step 2: Run focused smoke commands**

Run:

```bash
make backend-acceptance-smoke
make backend-runtime-smoke
make backend-websocket-smoke
make backend-chat-smoke
make desktop-acceptance-smoke
```

Expected: each command exits 0. `backend-chat-smoke` may skip the live chat turn when chat is unavailable.

- [x] **Step 3: Run repository checks**

Run: `make check`

Expected: pyright reports 0 errors and the full pytest suite passes.

- [x] **Step 4: Run doctor and desktop build**

Run: `make doctor` and `make desktop-build`.

Expected: both commands exit 0. `make doctor` may report optional warnings for unconfigured optional providers or missing local backups.

- [x] **Step 5: Commit and push**

```bash
git add docs/superpowers/specs/2026-07-06-smoke-contracts-design.md docs/superpowers/plans/2026-07-06-smoke-contracts.md Makefile scripts/integration/smoke_contracts.py scripts/integration/backend_acceptance_smoke.py scripts/integration/backend_runtime_smoke.py scripts/integration/backend_websocket_smoke.py scripts/integration/backend_chat_smoke.py scripts/integration/desktop_acceptance_smoke.py scripts/integration/provider_smoke.py tests/test_integration_smoke_contracts.py tests/test_backend_acceptance_smoke.py tests/test_backend_runtime_smoke.py tests/test_backend_websocket_smoke.py tests/test_backend_chat_smoke.py tests/test_desktop_acceptance_smoke.py tests/test_integration_smoke_profile.py tests/test_quality_gates.py
git commit -m "refactor: share integration smoke contracts"
git push origin main
```
