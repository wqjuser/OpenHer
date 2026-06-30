# Backend Live Chat Smoke Design

## Goal

Add an optional live-process smoke that validates a real `/api/chat` turn through the running FastAPI backend, then reads session status and persisted display history for the same client/persona.

## Scope

The smoke is a development and CI-adjacent diagnostic command. It must not run as part of default unit tests, and it must not fail merely because the developer has not configured an LLM key. When chat is unavailable, it should print a clear skipped result and exit 0.

## Architecture

Create `scripts/integration/backend_chat_smoke.py` as a small CLI that reuses `scripts.integration.backend_runtime_smoke` for port selection, uvicorn startup, `/api/status` readiness, auth headers, JSON decoding, and temporary `OPENHER_DATA_DIR` isolation. The new script owns only the chat-specific HTTP POST, session-status, and history assertions.

The smoke starts uvicorn with a temp runtime data directory. It checks `/api/status`; if `capabilities.chat.available` is false, it returns a `chat_turn` skipped result with the unavailable reason. If chat is available, it lists personas, sends a short deterministic Chinese prompt to `/api/chat`, checks the response shape, fetches `/api/session/{session_id}/status`, and verifies `/api/chat/history/{persona_id}` contains both user and assistant messages for the smoke client.

## Error Handling

External provider errors from `/api/chat` should fail the smoke with redacted output. Missing local LLM configuration should not be treated as a failure because local quality gates must remain runnable on machines without provider keys.

## Testing

Add source-contract tests for the new script, helper behavior tests for the POST JSON helper and skip parser, Makefile contract tests for compile and run targets, and README contract tests so the command stays discoverable. Run the live command locally with the configured DeepSeek/EverMemOS environment, plus the existing backend runtime/WebSocket/acceptance smokes and full `make check`.
