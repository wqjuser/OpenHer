# EverMemOS Projection Boundary Design

## Goal

Move EverMemOS response parsing and OpenHer memory text projection out of `EverMemOSClient` into a pure projection module.

## Current Problem

`providers/memory/evermemos/evermemos_client.py` still mixes two responsibilities after the protocol extraction:

- It sends HTTP requests, applies route fallback, logs latency, and records circuit breaker state.
- It also parses EverMemOS profile, atomic fact, episode, and foresight records into `SessionContext`, relevant-memory text snippets, and relationship priors.

The second group is deterministic data transformation. Keeping it inside the async HTTP client makes it harder to test response-shape compatibility and makes future EverMemOS schema changes riskier.

## Design

Add `providers/memory/evermemos/projection.py` with pure functions:

- `empty_session_context()` returns the zero-history `SessionContext`.
- `flatten_memory_results(results)` merges `{"result": {"memories": [...]}}` responses from session context load calls.
- `build_session_context_from_memories(memories, config)` converts raw memories into user profile text, episode summary, foresight text, counts, relationship depth, and pending foresight.
- `extract_search_memories(data)` normalizes cloud and legacy search response shapes into a flat memory list.
- `build_relevant_memory_projection(memories, config)` builds facts, episodes, and profile snippets with configured limits.
- `relationship_vector_from_context(ctx)` builds the 4D relationship prior from `SessionContext`.

`EverMemOSClient` will keep all side effects: availability checks, HTTP calls, fallback sequencing, logging, exceptions, and circuit breaker updates. It will delegate only deterministic response projection to the new module.

## Behavior

No public API changes are intended:

- `load_session_context(...)` still returns `SessionContext`.
- `search_relevant_memories(...)` still returns `(relevant_facts, relevant_episodes, relevant_profile)`.
- `relationship_vector(ctx)` still returns the same relationship prior dictionary.
- Empty or unavailable states still return empty strings or zero-context values.
- Logging remains in the client and uses counts exposed on `SessionContext` or projection results.

## Testing

Add focused projection tests for:

- Empty session context defaults.
- Session context formatting and derived counts from mixed profile, fact, episode, and foresight memories.
- Cloud search response flattening, including nested `atomic_facts`.
- Relevant memory tuple formatting and configured limits.
- Relationship vector trust and pending foresight calculation.

Update module boundary tests to assert `EverMemOSClient` imports `projection` and no longer defines projection helpers inline.
