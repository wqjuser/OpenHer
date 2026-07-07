# Legacy Compatibility Boundary Design

## Purpose

Reduce `main.py` and `server/bootstrap.py` compatibility responsibilities by extracting legacy global alias and helper-wrapper logic into a focused module.

## Problem

The runtime assembly is now mostly modular, but compatibility code is still split across entrypoint and bootstrap:

- `main.py` declares many legacy global service aliases.
- `main.py` defines old helper functions for proactive and session operations.
- `server/bootstrap.py` owns `sync_legacy_globals(...)`, even though that function is not startup assembly.

This keeps compatibility concerns mixed with app creation and lifecycle orchestration. It also makes the legacy surface harder to test directly.

## Scope

This phase moves only compatibility logic:

- Initial legacy global values for `main.py`.
- Runtime legacy global synchronization after startup and shutdown.
- Legacy proactive helper methods.
- Legacy session helper methods.

Out of scope:

- FastAPI route behavior.
- Startup or shutdown behavior.
- AppContext fields.
- Session manager, proactive service, or WebSocket behavior.
- Removing legacy symbols from `main.py`.

## Architecture

Add `server/legacy_compat.py` with:

- `initial_legacy_globals(context)`: returns the initial module globals that `main.py` historically exposed.
- `sync_legacy_globals(context, module_globals)`: updates module globals after startup/shutdown with current context services.
- `LegacyCompatibility`: a small context-bound adapter exposing the legacy helper methods.

`main.py` will import this module, install initial globals, bind helper method names to a `LegacyCompatibility(openher_context)` instance, and call `sync_legacy_globals(...)` from the lifespan hook.

`server/bootstrap.py` will no longer own legacy global synchronization.

## Compatibility

Behavior remains the same:

- Existing legacy global names remain exported by `main.py`.
- `_proactive_heartbeat_loop`, `_proactive_sweep`, `_deliver_proactive_msg`, `_persist_agent`, `_cleanup_expired_sessions`, `get_or_create_session`, and `remove_session` remain available from `main.py`.
- `get_or_create_session(...)` still raises `RuntimeError("Session manager is not initialized")` when no session manager exists.
- `_deliver_proactive_msg(...)` still raises `RuntimeError("Proactive service is not initialized")` when proactive service is unavailable.
- Lifespan startup/shutdown still refreshes legacy globals.

## Testing

- Add direct unit tests for legacy global initialization and synchronization.
- Add direct unit tests for legacy helper delegation and unavailable-service errors.
- Update bootstrap/main source boundary tests to require `server.legacy_compat` ownership.
- Run focused legacy/bootstrap tests, then full quality and smoke/build gates.
