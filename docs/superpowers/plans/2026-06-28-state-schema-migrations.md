# State Schema Migrations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move SQLite schema creation and upgrade logic out of `StateStore` into an idempotent migration module with explicit migration records.

**Architecture:** Add `engine/state_migrations.py` as the single owner of `genome_state`, `chat_summary`, `proactive_lock`, and `proactive_outbox` schema setup. `StateStore` will delegate initialization to `apply_state_schema_migrations(conn)` and keep only runtime persistence APIs. Migration functions will be idempotent so existing databases and new databases follow the same path safely.

**Tech Stack:** Python 3.11+, sqlite3, pytest, pyright.

---

### Task 1: Red Tests For State Schema Migration Boundary

**Files:**
- Create: `tests/test_state_migrations.py`

- [x] **Step 1: Write migration behavior tests**

Add tests that assert:
- A new `StateStore` database records migrations in `schema_migrations`.
- A legacy database with an old `genome_state` table upgrades in place without losing rows.
- Applying migrations twice is safe and does not duplicate migration records.
- `StateStore` delegates schema setup to `engine.state_migrations` and no longer owns direct `ALTER TABLE genome_state ADD COLUMN` logic.

- [x] **Step 2: Run tests and verify expected failure**

Run: `.venv/bin/python -m pytest tests/test_state_migrations.py -q`

Expected: FAIL because `engine.state_migrations` does not exist yet and `StateStore` still owns direct schema SQL.

### Task 2: Extract Idempotent Migration Module

**Files:**
- Create: `engine/state_migrations.py`
- Modify: `engine/state_store.py`

- [x] **Step 1: Add migration module**

Create `engine/state_migrations.py` with:
- `SCHEMA_MIGRATIONS`: ordered migration ids.
- `apply_state_schema_migrations(conn)`.
- `table_columns(conn, table_name)`.
- helper for `ALTER TABLE ... ADD COLUMN` only when a column is missing.

- [x] **Step 2: Move schema SQL**

Move the `CREATE TABLE IF NOT EXISTS` statements for `genome_state`, `chat_summary`, `proactive_lock`, and `proactive_outbox` into migration `001_initial_state_schema`.

- [x] **Step 3: Move legacy column upgrade**

Move `state_version`, `last_active_at`, and `interaction_cadence` upgrades into migration `002_genome_state_proactive_meta`.

- [x] **Step 4: Delegate from StateStore**

Replace `StateStore._create_tables()` with a thin call to `apply_state_schema_migrations(self._conn)`.

### Task 3: Verification And Delivery

**Files:**
- Test: `tests/test_state_migrations.py`
- Verify: full quality gate

- [x] **Step 1: Run migration tests**

Run: `.venv/bin/python -m pytest tests/test_state_migrations.py -q`

Expected: PASS.

- [x] **Step 2: Run focused state/proactive tests**

Run: `.venv/bin/python -m pytest tests/test_state_migrations.py tests/test_proactive_delivery.py tests/test_security_regressions.py::SessionManagerRegressionTests tests/test_security_regressions.py::ProactiveDeliveryContractTests -q`

Expected: PASS.

- [x] **Step 3: Run full verification**

Run:
- `source .venv/bin/activate && make check`
- `.venv/bin/python -m py_compile engine/state_migrations.py engine/state_store.py tests/test_state_migrations.py`
- `cd desktop/OpenHer && swift build`

Expected: all commands exit 0.

- [x] **Step 4: Commit branch**

Run:
```bash
git add engine/state_migrations.py engine/state_store.py tests/test_state_migrations.py docs/superpowers/plans/2026-06-28-state-schema-migrations.md
git commit -m "refactor: add state schema migrations"
```

Expected: branch contains the migration boundary commit.

- [x] **Step 5: Merge and push**

Run:
```bash
git switch main
git pull --ff-only
git merge --no-ff codex/state-schema-migrations -m "merge: state schema migrations"
git push origin main
```

Expected: `main` contains the migration boundary merge commit and is pushed to `origin/main`.
