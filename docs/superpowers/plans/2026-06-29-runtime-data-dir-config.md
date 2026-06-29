# Runtime Data Directory Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a generic `OPENHER_DATA_DIR` runtime override so live backend smokes and deployments can isolate SQLite/genome state without changing provider configuration.

**Architecture:** Keep `.data` as the production default, but make `server.bootstrap` resolve one canonical runtime data directory at startup. Preserve explicit absolute memory database paths, while remapping the default `.data/memory.db` under the runtime directory when an override is present. Update live-process smoke scripts to launch uvicorn with a temporary `OPENHER_DATA_DIR` so tests do not touch the developer's persistent `.data`.

**Tech Stack:** Python 3.11+, FastAPI/Uvicorn startup assembly, pytest, Pyright, shell Make targets.

---

### Task 1: Bootstrap Runtime Path Contract

**Files:**
- Modify: `tests/test_server_bootstrap.py`
- Modify: `server/bootstrap.py`

- [ ] **Step 1: Write failing tests for default, absolute, and relative runtime data directory resolution**

```python
def test_runtime_data_dir_defaults_to_repo_data_dir(monkeypatch, tmp_path):
    import server.bootstrap as bootstrap

    monkeypatch.delenv("OPENHER_DATA_DIR", raising=False)

    assert bootstrap._runtime_data_dir(tmp_path) == tmp_path / ".data"


def test_runtime_data_dir_accepts_absolute_override(monkeypatch, tmp_path):
    import server.bootstrap as bootstrap

    data_dir = tmp_path / "isolated"
    monkeypatch.setenv("OPENHER_DATA_DIR", str(data_dir))

    assert bootstrap._runtime_data_dir(tmp_path) == data_dir


def test_runtime_data_dir_resolves_relative_override_against_repo(monkeypatch, tmp_path):
    import server.bootstrap as bootstrap

    monkeypatch.setenv("OPENHER_DATA_DIR", ".runtime-smoke")

    assert bootstrap._runtime_data_dir(tmp_path) == tmp_path / ".runtime-smoke"
```

- [ ] **Step 2: Run tests to verify they fail because `_runtime_data_dir` does not exist**

Run: `source .venv/bin/activate && python -m pytest tests/test_server_bootstrap.py::test_runtime_data_dir_defaults_to_repo_data_dir -q`

Expected: FAIL with `AttributeError: module 'server.bootstrap' has no attribute '_runtime_data_dir'`.

- [ ] **Step 3: Implement runtime path helpers**

Add these helpers in `server/bootstrap.py` after `_repo_root()`:

```python
def _runtime_data_dir(base_dir: Path) -> Path:
    configured = os.getenv("OPENHER_DATA_DIR", "").strip()
    if not configured:
        return base_dir / ".data"

    data_dir = Path(configured).expanduser()
    if not data_dir.is_absolute():
        data_dir = base_dir / data_dir
    return data_dir


def _runtime_path(base_dir: Path, data_dir: Path, configured_path: str) -> Path:
    path = Path(configured_path).expanduser()
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == ".data":
        return data_dir.joinpath(*path.parts[1:])
    return base_dir / path
```

- [ ] **Step 4: Use the runtime directory for genome, state, chat log, and default SoulMem SQLite**

Replace `data_dir = base_dir / ".data"` with `data_dir = _runtime_data_dir(base_dir)`, and resolve `soulmem_db` through `_runtime_path(base_dir, data_dir, mem_prov_cfg["soulmem"]["db_path"])`.

- [ ] **Step 5: Run bootstrap tests**

Run: `source .venv/bin/activate && python -m pytest tests/test_server_bootstrap.py -q`

Expected: PASS.

### Task 2: Live Smoke Isolation

**Files:**
- Modify: `tests/test_backend_runtime_smoke.py`
- Modify: `tests/test_backend_websocket_smoke.py`
- Modify: `scripts/integration/backend_runtime_smoke.py`
- Modify: `scripts/integration/backend_websocket_smoke.py`

- [ ] **Step 1: Write source-contract tests for temporary runtime data directories**

Add runtime smoke assertions:

```python
def test_backend_runtime_smoke_uses_temporary_data_dir():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "TemporaryDirectory" in source
    assert "OPENHER_DATA_DIR" in source
    assert "env_overrides" in source
```

Add WebSocket smoke assertions:

```python
def test_backend_websocket_smoke_uses_temporary_data_dir():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "TemporaryDirectory" in source
    assert "OPENHER_DATA_DIR" in source
    assert "env_overrides" in source
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_backend_runtime_smoke.py::test_backend_runtime_smoke_uses_temporary_data_dir tests/test_backend_websocket_smoke.py::test_backend_websocket_smoke_uses_temporary_data_dir -q`

Expected: FAIL because the smoke scripts do not pass `OPENHER_DATA_DIR`.

- [ ] **Step 3: Add env overrides to the shared runtime smoke launcher**

Change `start_server` to:

```python
def start_server(port: int, *, env_overrides: dict[str, str] | None = None) -> tuple[subprocess.Popen[str], TextIO]:
    log_file = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    if env_overrides:
        env.update(env_overrides)
```

Wrap `run_smoke` with:

```python
with tempfile.TemporaryDirectory(prefix="openher-runtime-smoke-") as data_dir:
    process, log_file = start_server(port, env_overrides={"OPENHER_DATA_DIR": data_dir})
```

- [ ] **Step 4: Add temp data isolation to WebSocket smoke**

Import `tempfile` and wrap its server startup with:

```python
with tempfile.TemporaryDirectory(prefix="openher-websocket-smoke-") as data_dir:
    process, log_file = backend_runtime_smoke.start_server(
        port,
        env_overrides={"OPENHER_DATA_DIR": data_dir},
    )
```

- [ ] **Step 5: Run smoke tests**

Run: `source .venv/bin/activate && python -m pytest tests/test_backend_runtime_smoke.py tests/test_backend_websocket_smoke.py -q`

Expected: PASS.

### Task 3: Documentation and Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document `OPENHER_DATA_DIR`**

Add a short configuration note that `.data` remains the default and `OPENHER_DATA_DIR=/path/to/runtime-data` can isolate a run or test environment.

- [ ] **Step 2: Run focused live smoke commands**

Run:

```bash
source .venv/bin/activate
make backend-runtime-smoke
make backend-websocket-smoke
make backend-acceptance-smoke
```

Expected: all exit 0.

- [ ] **Step 3: Run full gates**

Run:

```bash
source .venv/bin/activate
make check
swift build --package-path desktop/OpenHer
make integration-smoke
```

Expected: all exit 0, with provider integrations allowed to skip unavailable optional media providers.

- [ ] **Step 4: Commit, merge, and push**

Run:

```bash
git status --short
git add docs/superpowers/plans/2026-06-29-runtime-data-dir-config.md tests/test_server_bootstrap.py tests/test_backend_runtime_smoke.py tests/test_backend_websocket_smoke.py server/bootstrap.py scripts/integration/backend_runtime_smoke.py scripts/integration/backend_websocket_smoke.py README.md
git commit -m "refactor: isolate runtime smoke data directory"
git checkout main
git merge --ff-only codex/runtime-data-dir-config
git push origin main
```

Expected: branch fast-forwards and push succeeds.
