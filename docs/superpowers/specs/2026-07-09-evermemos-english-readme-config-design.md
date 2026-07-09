# EverMemOS English README Config Design

## Goal

Make the English README match the current EverMemOS cloud configuration behavior.

## Design

Cloud EverMemOS setup should tell users to set only `EVERMEMOS_API_KEY`; OpenHer already uses the default cloud URL. `EVERMEMOS_BASE_URL` should be documented only for self-hosted or private gateway setups.

Add one README contract assertion so the stale cloud base URL does not come back.
