# EverMemOS Cloud URL Alias Design

## Goal

Treat the stale documented EverMemOS cloud URL `https://api.evermind.ai/v1` as the current cloud API URL.

## Design

Extend the existing `normalize_evermemos_base_url()` helper in `providers/config.py`. It already owns EverMemOS URL normalization and is used by both central config and `EverMemOSClient`.

No new URL parser or migration layer. This is one known legacy cloud alias.
