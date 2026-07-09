# Memory Placeholder Secret Design

## Goal

Do not treat copied EverMemOS placeholder API keys as configured memory secrets.

## Design

Reuse the existing provider placeholder secret filter in `providers/config.py` for memory API keys. This keeps the behavior consistent with LLM, TTS, and image providers without adding a second filtering rule.

If the user sets only `EVERMEMOS_API_KEY=your_evermemos_api_key_here` or `MEMORY_API_KEY=your_current_memory_api_key_here`, memory stays disabled and no cloud default URL is inferred from that placeholder.
