# EverMemOS Protocol Boundary Design

## Goal

Extract EverMemOS request-shape rules from `EverMemOSClient` into a small protocol module without changing runtime behavior.

## Current Problem

`providers/memory/evermemos/evermemos_client.py` owns too many responsibilities:

- HTTP client lifecycle and connection verification.
- Cloud, self-hosted, and legacy route fallback rules.
- Request payload construction for store, search, health, and memory get calls.
- Response parsing, logging, and circuit breaker updates.

That makes the client harder to verify when EverMemOS changes API shapes. It also keeps official cloud payload rules mixed with fallback and logging logic.

## Design

Add `providers/memory/evermemos/protocol.py` as a pure request protocol boundary. It will expose constants and builder functions for:

- Official cloud search and health payloads using `filters`, `query`, `method`, and `top_k`.
- OSS search fallback payloads using direct `user_id`, `app_id`, `project_id`, optional `filters.session_id`, and profile inclusion.
- Legacy search fallback payloads using `retrieve_method` and optional `group_ids`.
- Cloud batch memory storage payloads.
- Legacy single-message storage payloads.
- Memory get payloads for v1 and compatibility fallback calls.

`EverMemOSClient` will keep all side effects: sending requests, choosing fallback based on response status, parsing returned data, logging, and circuit breaker updates. It will import protocol builders instead of constructing these bodies inline.

## Behavior

No provider behavior changes are intended:

- The first search call remains `POST /memories/search` with the official cloud body.
- Health verification remains a lightweight `POST /memories/search`.
- Store calls still try `POST /memories`, then `POST /memory/add`, then legacy flat `POST /memories`.
- Session context load still tries v1 get routes first and compatibility payloads only after 404 or 405.
- Existing environment and config precedence stays untouched.

## Testing

Add focused protocol tests for payload builders, then update the existing EverMemOS module boundary test to require the client to delegate protocol construction to `providers.memory.evermemos.protocol`. Run EverMemOS-focused tests before the full repository gate.
