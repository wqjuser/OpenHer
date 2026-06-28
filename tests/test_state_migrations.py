"""StateStore SQLite schema migration tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sqlite_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def table_names(db_path: Path) -> set[str]:
    with sqlite_connection(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row["name"] for row in rows}


def table_columns(db_path: Path, table_name: str) -> set[str]:
    with sqlite_connection(db_path) as conn:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def recorded_migration_ids(db_path: Path) -> list[str]:
    with sqlite_connection(db_path) as conn:
        rows = conn.execute("SELECT id FROM schema_migrations ORDER BY id").fetchall()
    return [row["id"] for row in rows]


def test_state_store_records_schema_migrations_for_new_database(tmp_path: Path):
    from engine.state_migrations import SCHEMA_MIGRATIONS
    from engine.state_store import StateStore

    db_path = tmp_path / "openher.db"

    store = StateStore(str(db_path))
    store.close()

    assert recorded_migration_ids(db_path) == [migration.id for migration in SCHEMA_MIGRATIONS]
    assert {
        "schema_migrations",
        "genome_state",
        "chat_summary",
        "proactive_lock",
        "proactive_outbox",
    }.issubset(table_names(db_path))
    assert {
        "state_version",
        "last_active_at",
        "interaction_cadence",
    }.issubset(table_columns(db_path, "genome_state"))


def test_state_store_upgrades_legacy_genome_state_without_losing_rows(tmp_path: Path):
    from engine.state_migrations import SCHEMA_MIGRATIONS
    from engine.state_store import StateStore

    db_path = tmp_path / "legacy-openher.db"
    with sqlite_connection(db_path) as conn:
        conn.executescript("""
            CREATE TABLE genome_state (
                user_id TEXT NOT NULL,
                persona_id TEXT NOT NULL,
                agent_data TEXT DEFAULT '{}',
                metabolism_data TEXT DEFAULT '{}',
                updated_at REAL DEFAULT 0,
                PRIMARY KEY (user_id, persona_id)
            );
        """)
        conn.execute(
            """
            INSERT INTO genome_state (user_id, persona_id, agent_data, metabolism_data, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("user-1", "luna", '{"age": 3}', '{"frustration": 0}', 123.0),
        )

    store = StateStore(str(db_path))
    store.close()

    assert recorded_migration_ids(db_path) == [migration.id for migration in SCHEMA_MIGRATIONS]
    assert {
        "chat_summary",
        "proactive_lock",
        "proactive_outbox",
    }.issubset(table_names(db_path))
    assert {
        "state_version",
        "last_active_at",
        "interaction_cadence",
    }.issubset(table_columns(db_path, "genome_state"))

    with sqlite_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT user_id, persona_id, agent_data, metabolism_data,
                   state_version, last_active_at, interaction_cadence, updated_at
            FROM genome_state
            WHERE user_id=? AND persona_id=?
            """,
            ("user-1", "luna"),
        ).fetchone()

    assert dict(row) == {
        "user_id": "user-1",
        "persona_id": "luna",
        "agent_data": '{"age": 3}',
        "metabolism_data": '{"frustration": 0}',
        "state_version": 0,
        "last_active_at": 0.0,
        "interaction_cadence": 0.0,
        "updated_at": 123.0,
    }


def test_state_schema_migrations_are_idempotent(tmp_path: Path):
    from engine.state_migrations import SCHEMA_MIGRATIONS, apply_state_schema_migrations

    db_path = tmp_path / "idempotent.db"
    with sqlite_connection(db_path) as conn:
        apply_state_schema_migrations(conn)
        apply_state_schema_migrations(conn)

    assert recorded_migration_ids(db_path) == [migration.id for migration in SCHEMA_MIGRATIONS]


def test_state_store_delegates_schema_setup_to_migration_module():
    state_store_source = (ROOT / "engine" / "state_store.py").read_text(encoding="utf-8")

    assert "from engine.state_migrations import apply_state_schema_migrations" in state_store_source
    assert "apply_state_schema_migrations(self._conn)" in state_store_source
    assert "ALTER TABLE genome_state ADD COLUMN" not in state_store_source
    assert "CREATE TABLE IF NOT EXISTS genome_state" not in state_store_source
