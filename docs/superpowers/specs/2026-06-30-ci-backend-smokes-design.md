# CI Backend Smokes Design

## Goal

Run OpenHer's backend smoke commands in GitHub Actions so CI catches real FastAPI startup, HTTP route wiring, WebSocket error contracts, and REST chat degradation behavior.

## Scope

This change only affects CI orchestration and quality-gate tests. It does not make CI call external provider APIs. `make integration-smoke` remains an explicit local/manual command because it can call real LLM and EverMemOS services.

## Architecture

Extend the existing `.github/workflows/ci.yml` backend matrix job with a backend smoke step after the normal static checks, compile checks, pytest suite, and whitespace check. The step runs `make backend-acceptance-smoke`, `make backend-runtime-smoke`, `make backend-websocket-smoke`, and `make backend-chat-smoke`.

The live-process smoke scripts already isolate runtime state with temporary `OPENHER_DATA_DIR` directories and clean up uvicorn children. `backend-chat-smoke` exits successfully with a skipped chat result when CI has no LLM key, so the workflow validates startup and degraded chat capability without requiring secrets.

## Testing

Add a repository quality-gate test requiring the CI workflow to include all four backend smoke commands. Verify the focused quality-gate test fails before editing CI, then passes after the workflow update. Run `make check`, all backend smoke commands locally, Swift build, and integration smoke before merging.
