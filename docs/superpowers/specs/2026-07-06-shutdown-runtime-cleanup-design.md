# Shutdown Runtime Cleanup Design

## Purpose

Reduce `server/bootstrap.py` lifecycle responsibility by extracting shutdown cleanup into a focused runtime module.

## Problem

`startup()` now delegates provider, persistence, skill, session, and background service assembly to focused runtime builders. `shutdown()` is still different: it directly cancels background tasks, stops cron, persists sessions, closes stores, and closes EverMemOS sessions.

That makes shutdown behavior harder to test in isolation and keeps low-level cleanup ordering embedded in bootstrap.

## Scope

This phase moves only shutdown cleanup:

- Cancel the proactive heartbeat task when it is still running.
- Stop the cron scheduler.
- Persist active session state before closing the state store.
- Close state, memory, and chat log stores.
- Close active EverMemOS sessions for active agents.
- Return the existing shutdown completion message for bootstrap to print.

Out of scope:

- Startup assembly.
- Resource close ordering changes.
- Error recovery policy changes.
- Session manager behavior.
- EverMemOS client behavior.
- Legacy global sync behavior.

## Architecture

Add `server/shutdown_runtime.py` with:

- `shutdown_runtime_services(context)`: coordinates the full shutdown cleanup sequence and returns printable messages.
- `cancel_proactive_task(context)`: cancels and awaits the proactive task, then clears it from the context.
- `close_evermemos_sessions(evermemos, session_manager)`: closes active EverMemOS sessions when the cloud memory client is available.

`server/bootstrap.py::shutdown()` delegates to `shutdown_runtime_services(context)` and prints returned messages. This keeps FastAPI lifespan hooks stable while making cleanup independently testable.

## Compatibility

Behavior remains the same:

- Already-completed proactive tasks are not cancelled.
- Running proactive tasks are cancelled and `asyncio.CancelledError` is swallowed.
- Cron scheduler is stopped when present.
- `SessionManager.persist_all()` runs before `StateStore.close()`.
- `MemoryStore.close()` and `ChatLogStore.close()` still run when present.
- EverMemOS close-session calls still use each active agent's `evermemos_uid`, persona id, and `_group_id`.
- EverMemOS close-session exceptions are gathered with `return_exceptions=True`, preserving the current non-fatal shutdown behavior.

## Testing

- Add direct unit tests for shutdown runtime cleanup ordering and optional dependency handling.
- Update bootstrap source boundary tests to require `server.shutdown_runtime` delegation.
- Run focused shutdown/bootstrap tests, then full quality and smoke/build gates.
