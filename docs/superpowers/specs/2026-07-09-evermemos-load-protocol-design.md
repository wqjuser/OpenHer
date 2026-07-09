# EverMemOS Load Protocol Design

## Goal

Move the remaining session-load request-shape details from `EverMemOSClient` into the existing `protocol.py`.

## Design

Add pure helpers for:

- Mapping OpenHer memory types to v1 EverMemOS memory types.
- Resolving the response collection key.
- Building the legacy `GET /memories` body.

No new service layer. The client keeps HTTP calls, fallback decisions, logging, and circuit breaker state.

## Behavior

No route order or public API changes. `load_session_context()` still queries profile, event log, episodic memory, and foresight in the same order and returns the same `SessionContext`.
