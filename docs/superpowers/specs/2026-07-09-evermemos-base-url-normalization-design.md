# EverMemOS Base URL Normalization Design

## Goal

Keep EverMemOS cloud URLs on `/api/v1` even when old `/api/v0` values are supplied by config or env.

## Design

Add one shared normalization helper in `providers/config.py` and use it from both central memory config resolution and `EverMemOSClient`.

No new URL module. The only special case is the known EverMemOS cloud `/api/v0` endpoint; local/custom hosts keep the existing auto-append `/api/v1` behavior when no `/api/` segment is present.
