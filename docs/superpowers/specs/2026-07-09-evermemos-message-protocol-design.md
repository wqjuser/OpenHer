# EverMemOS Message Protocol Design

## Goal

Keep EverMemOS request-shape construction in `providers/memory/evermemos/protocol.py`.

## Design

Extend the existing protocol module with pure builders for:

- OSS health-check fallback body.
- `/memory/flush` body.
- turn, proactive, and session-flush message lists.

`EverMemOSClient` will keep HTTP calls, logging, fallback decisions, and circuit breaker state. No new service layer is needed.

## Behavior

No public API or route order changes:

- `verify_connection()` still tries cloud search first, then OSS search on 404 or 405.
- `_post_memories()` still flushes only after `/memory/add` succeeds.
- `store_turn()`, `store_proactive_turn()`, and `close_session()` still send the same message shapes.

## Tests

Add protocol tests for exact bodies/messages, then update the client to use those builders and run the EverMemOS focused tests plus repository gates.
