# Persistence Runtime Assembly Design

## Purpose

Reduce `server/bootstrap.py` startup responsibility by extracting runtime data directory, local stores, local memory, and EverMemOS client assembly into a focused persistence runtime module.

## Problem

`startup()` still owns persistence details after provider assembly was extracted:

- It resolves `OPENHER_DATA_DIR`.
- It maps default `.data/...` paths to the active runtime data directory.
- It creates the genome runtime directory.
- It constructs `StateStore`, `ChatLogStore`, and `MemoryStore`.
- It reads memory provider config inline.
- It constructs and verifies the optional EverMemOS client.
- It prints the fallback message when EverMemOS is disabled.

These details make bootstrap harder to read and harder to unit-test. They also mix process orchestration with filesystem and persistence construction.

## Scope

This phase moves only persistence runtime assembly:

- Runtime data directory resolution.
- Runtime path remapping for configured local store paths.
- Genome data directory creation.
- `StateStore`, `ChatLogStore`, and `MemoryStore` construction.
- EverMemOS configuration, construction, optional verification, and disabled fallback message.

Out of scope:

- Session manager construction.
- Chat API service construction.
- WebSocket services.
- Cron/proactive service construction.
- Data lifecycle CLI behavior.
- Health/status response contracts.

## Architecture

Add `server/persistence_runtime.py` with:

- `PersistenceRuntimeServices`: dataclass containing runtime data paths and assembled persistence services.
- `resolve_runtime_data_dir(base_dir, configured=None)`: resolves `OPENHER_DATA_DIR` with the same relative/absolute semantics as bootstrap has today.
- `resolve_runtime_path(base_dir, data_dir, configured_path)`: preserves current `.data/...` remapping behavior.
- `build_persistence_runtime_services(base_dir, ...)`: creates local stores, initializes optional EverMemOS, verifies it when available, and returns informational messages instead of printing.

`startup()` calls `await build_persistence_runtime_services(base_dir)`, assigns the returned services to `AppContext`, and prints returned messages. Bootstrap keeps session, WebSocket, cron, and proactive orchestration.

The builder accepts optional configs and factory callables so tests can exercise behavior without opening real SQLite databases or contacting EverMemOS.

## Compatibility

Behavior remains the same:

- Missing `OPENHER_DATA_DIR` resolves to `<repo>/.data`.
- Relative `OPENHER_DATA_DIR` resolves against the repo root.
- Absolute `OPENHER_DATA_DIR` is preserved.
- Configured `.data/...` local memory paths are remapped into the active runtime data directory.
- Custom relative local memory paths still resolve against the repo root.
- Genome data directory is still created under the active runtime data directory.
- State and chat stores still use `openher.db` and `chat.db` inside the active runtime data directory.
- EverMemOS is still constructed when enabled and either `base_url` or `api_key` is configured.
- Available EverMemOS clients are still verified during startup.
- Disabled EverMemOS still falls back to local `MemoryStore` and prints the same informational message.

## Testing

- Add unit tests for runtime data dir and runtime path resolution in the new module.
- Add unit tests for persistence service assembly with injected fake factories.
- Add an async unit test verifying EverMemOS construction and connection verification.
- Update bootstrap source boundary tests so `server/bootstrap.py` delegates persistence construction to `server.persistence_runtime`.
- Run focused persistence/bootstrap tests, full quality gates, backend runtime smokes, backend chat smoke, desktop acceptance smoke, and desktop build.
