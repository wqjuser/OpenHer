# Persona API Service Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move persona metadata and persona media lookup rules out of FastAPI routes into a focused service boundary.

**Architecture:** Add `server/persona_api_service.py` with `PersonaApiService`, a `PersonaMediaFile` dataclass, and small service exceptions. `server/routes/persona.py` will keep HTTP status mapping and `FileResponse` construction while delegating persona listing, description summarization, avatar lookup, and idimage media lookup to the service. `AppContext` and bootstrap will expose a configured service, with route-level fallback for unit tests that construct partial contexts.

**Tech Stack:** Python 3.11+, FastAPI, pytest, existing `PersonaLoader` and `PersonaInfo` schema.

---

### Task 1: Lock Persona API Service Behavior With Failing Tests

**Files:**
- Create: `tests/test_persona_api_service.py`
- Verify: `server/routes/persona.py`
- Verify: `server/context.py`
- Verify: `server/bootstrap.py`

- [x] **Step 1: Write persona list summary test**

Create fake persona objects with:

```python
SimpleNamespace(
    name="Luna",
    name_zh="露娜",
    age=24,
    gender="female",
    mbti="INFP",
    tags=["artist"],
    tags_zh=["画家"],
    bio={"zh": "第一句。第二句。"},
    personality="fallback personality",
)
```

Assert `PersonaApiService.list_personas()` returns a `PersonaInfo` whose description is `第一句`, whose avatar URL is present when `avatar.png` exists, and whose `has_front` and `has_awakening_video` flags reflect files in `idimage/`.

- [x] **Step 2: Write media lookup tests**

Assert:
- `get_avatar("luna")` returns a media file with `filename == "luna_avatar.png"`;
- `get_persona_media("luna", "awakening")` prefers `awakening.mp4`;
- `get_persona_media("luna", "wakening")` can find `wakening.mp4`;
- invalid media type raises `PersonaApiUnknownMediaType`;
- missing file raises `PersonaApiMediaNotFound`.

- [x] **Step 3: Write service-unavailable and route delegation tests**

Assert:
- missing persona loader raises `PersonaApiServiceUnavailable`;
- `server/routes/persona.py` imports `PersonaApiService`, calls `service.list_personas()`, `service.get_persona_media(...)`, and `service.get_avatar(...)`;
- `server/routes/persona.py` no longer imports `re` or constructs `PersonaInfo` directly;
- `server/context.py` has a typed `persona_api_service` field;
- `server/bootstrap.py` constructs `PersonaApiService`.

- [x] **Step 4: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_persona_api_service.py -q`

Expected: FAIL because `server.persona_api_service` does not exist and persona routes still own the persona API rules.

### Task 2: Add PersonaApiService

**Files:**
- Create: `server/persona_api_service.py`
- Test: `tests/test_persona_api_service.py`

- [x] **Step 1: Implement media file dataclass**

Create:

```python
@dataclass(frozen=True)
class PersonaMediaFile:
    path: str
    media_type: str
    filename: str | None = None
```

- [x] **Step 2: Implement service exceptions**

Create:

```python
class PersonaApiServiceUnavailable(RuntimeError): ...
class PersonaApiUnknownMediaType(ValueError): ...
class PersonaApiMediaNotFound(FileNotFoundError): ...
```

- [x] **Step 3: Implement list_personas**

`PersonaApiService.list_personas()` should:
- raise `PersonaApiServiceUnavailable("Persona loader is not initialized")` when no loader is configured;
- call `persona_loader.load_all()`;
- derive the description from `bio["zh"]`, `bio["en"]`, `personality`, or `""`;
- split at Chinese sentence punctuation or newline and limit to 120 characters;
- set `avatar_url` only when `avatar.png` exists;
- set `has_front` when `idimage/front.png` exists;
- set `has_awakening_video` when either `idimage/awakening.mp4` or `idimage/wakening.mp4` exists.

- [x] **Step 4: Implement avatar and idimage media lookup**

`get_avatar(persona_id)` should return `PersonaMediaFile` for `avatar.png` with filename `<persona_id>_avatar.png`, or raise `PersonaApiMediaNotFound("Avatar not found")`.

`get_persona_media(persona_id, media_type)` should use this exact map:

```python
{
    "front": ["front.png"],
    "face": ["face.png"],
    "awakened": ["awakened.png"],
    "awakening": ["awakening.mp4", "wakening.mp4"],
    "wakening": ["wakening.mp4"],
}
```

Invalid media types raise `PersonaApiUnknownMediaType(f"Unknown media type: {media_type}")`; missing files raise `PersonaApiMediaNotFound(f"Media not found: {persona_id}/{media_type}")`.

- [x] **Step 5: Run service tests**

Run: `.venv/bin/python -m pytest tests/test_persona_api_service.py -q`

Expected: service behavior tests pass; route/context/bootstrap structural tests may still fail until Task 3.

### Task 3: Delegate Routes And Bootstrap Service

**Files:**
- Modify: `server/routes/persona.py`
- Modify: `server/context.py`
- Modify: `server/bootstrap.py`
- Test: `tests/test_persona_api_service.py`
- Test: `tests/test_server_context.py`
- Test: `tests/test_server_routes.py`
- Test: `tests/test_security_regressions.py`

- [x] **Step 1: Add service to app context**

Import `PersonaApiService` in `server/context.py` and add:

```python
persona_api_service: PersonaApiService | None = None
```

- [x] **Step 2: Build service during startup**

Import `PersonaApiService` in `server/bootstrap.py` and after `context.persona_loader` is created, set:

```python
context.persona_api_service = PersonaApiService(
    persona_loader=context.persona_loader,
    personas_dir=base_dir / "persona" / "personas",
)
```

Also expose it through `sync_legacy_globals()`.

- [x] **Step 3: Thin persona routes**

In `server/routes/persona.py`, construct fallback service with:

```python
service = ctx.persona_api_service or PersonaApiService(
    persona_loader=ctx.persona_loader,
    personas_dir=PERSONAS_DIR,
)
```

Map:
- `PersonaApiServiceUnavailable` to HTTP 503;
- `PersonaApiUnknownMediaType` to HTTP 400;
- `PersonaApiMediaNotFound` to HTTP 404.

Return:

```python
return {"personas": [persona.model_dump() for persona in personas]}
return FileResponse(media.path, media_type=media.media_type, filename=media.filename)
```

- [x] **Step 4: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_persona_api_service.py tests/test_server_context.py tests/test_server_routes.py tests/test_security_regressions.py -q`

Expected: all selected tests pass.

### Task 4: Full Verification And Release

**Files:**
- Verify: `server/persona_api_service.py`
- Verify: `server/routes/persona.py`
- Verify: `server/context.py`
- Verify: `server/bootstrap.py`
- Verify: `tests/test_persona_api_service.py`

- [x] **Step 1: Run static and compile checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

Run: `.venv/bin/python -m py_compile server/persona_api_service.py server/routes/persona.py server/context.py server/bootstrap.py tests/test_persona_api_service.py`

Expected: exit code 0.

- [x] **Step 2: Run full tests**

Run: `.venv/bin/python -m pytest tests/ -q`

Expected: full suite passes with the known skipped WebSocket integration test unchanged.

- [x] **Step 3: Run repository hygiene checks**

Run: `.venv/bin/python -m compileall agent engine memory persona providers server skills tests main.py wechat_adapter.py`

Expected: exit code 0.

Run: `git diff --check`

Expected: exit code 0.

- [x] **Step 4: Run service smoke**

Start: `PORT=8783 ./run.sh`

Check:
- `GET /api/status`;
- `GET /api/personas`;
- `GET /api/persona/luna/media/front`;
- WebSocket `demo_presets`;
- `POST /api/chat`.

Expected: backend starts and existing persona, media, websocket, and chat paths still run normally.

- [x] **Step 5: Commit, merge, and push**

Run:

```bash
git add server/persona_api_service.py server/routes/persona.py server/context.py server/bootstrap.py tests/test_persona_api_service.py docs/superpowers/plans/2026-06-25-persona-api-service-boundary.md
git commit -m "refactor: extract persona api service boundary"
git switch main
git pull --ff-only
git merge --no-ff codex/persona-api-service-boundary -m "merge: persona api service boundary"
git push origin main
```

### Self-Review

- Spec coverage: The plan extracts persona listing and persona media lookup while leaving HTTP response construction in routes.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `PersonaApiService`, `PersonaMediaFile`, and exception names are consistent across service, route, context, bootstrap, and tests.
