# Repository Guidelines

## Project Structure & Module Organization

OpenHer is a Python 3.11+ backend with an optional macOS Swift client. Core server entry points are `main.py` and `wechat_adapter.py`. Runtime logic is split across `agent/`, `engine/`, `memory/`, `persona/`, `providers/`, and `skills/`. Tests live in `tests/` as `test_*.py`. Project docs and media assets are under `docs/`, personas under `persona/personas/`, benchmark scripts under `scripts/benchmark/`, and the Swift package under `desktop/OpenHer/`.

## Build, Test, and Development Commands

- `bash setup.sh`: create `.venv`, install `requirements.txt`, copy `.env.example` to `.env`, and prepare `.data/`.
- `source .venv/bin/activate`: activate the local Python environment before development.
- `python main.py` or `./run.sh`: start the backend on port `8000`; set `PORT=9000 ./run.sh` to override.
- `./run.sh --bg`: run the backend in the background with logs in `.data/server.log`.
- `python -m pytest tests/ -v`: run the Python test suite.
- `pyright`: run static type checks using `pyrightconfig.json` if Pyright is installed.
- `cd desktop/OpenHer && ./run.sh`: build and launch the macOS client, copying `OpenHer.app` to the repo root.

## Coding Style & Naming Conventions

Follow PEP 8 with 4-space indentation for Python. Use type hints for new code, `async/await` for I/O paths, `snake_case.py` files, `snake_case` functions and variables, `PascalCase` classes, and `UPPER_SNAKE_CASE` constants. Keep persona-engine changes generic; feature-specific behavior should usually live in the Skill Engine or provider adapters. Swift sources follow standard Swift naming with `PascalCase` types and `camelCase` members.

## Testing Guidelines

Use `pytest` and `pytest-asyncio`; `pytest.ini` sets `asyncio_mode = auto` and `testpaths = tests`. Name new test files `test_<feature>.py` and keep external provider, memory, and network calls mocked unless a test explicitly documents an integration requirement. Run targeted tests with `python -m pytest tests/test_skill_engine.py -v` while iterating, then run the full suite before a PR.

## Commit & Pull Request Guidelines

Git history uses Conventional Commit prefixes such as `feat:`, `fix:`, `docs:`, `refactor:`, and `test:`. Keep commits focused and imperative, for example `fix: preserve persona state after reconnect`. PRs should describe what changed and why, link related issues, include screenshots or recordings for UI changes, and note test results.

## Security & Configuration Tips

Never commit `.env`, `.data/`, API keys, generated logs, or local app bundles. Start from `.env.example`, configure at least one LLM provider key or Ollama, and redact secrets from bug reports and test fixtures.
