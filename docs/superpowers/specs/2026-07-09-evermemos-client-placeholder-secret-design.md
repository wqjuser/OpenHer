# EverMemOS Client Placeholder Secret Design

## Goal

Do not let `EverMemOSClient` send copied placeholder API keys from environment fallbacks.

## Design

Reuse the existing provider placeholder secret filter from `providers.config` inside `EverMemOSClient.__init__`. This keeps direct client construction consistent with `get_memory_config()` without adding a second rule.

If only `EVERMEMOS_API_KEY=your_evermemos_api_key_here` or `MEMORY_API_KEY=your_current_memory_api_key_here` is set, the client may still initialize for local/self-hosted use, but it must not attach an Authorization header.
