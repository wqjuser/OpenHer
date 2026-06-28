"""Versioned SQLite schema migrations for StateStore."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import sqlite3
import time


@dataclass(frozen=True)
class SchemaMigration:
    """One idempotent StateStore schema migration."""

    id: str
    runner: Callable[[sqlite3.Connection], None]


INITIAL_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS genome_state (
    user_id TEXT NOT NULL,
    persona_id TEXT NOT NULL,
    agent_data TEXT DEFAULT '{}',
    metabolism_data TEXT DEFAULT '{}',
    state_version INTEGER DEFAULT 0,
    last_active_at REAL DEFAULT 0,
    interaction_cadence REAL DEFAULT 0,
    updated_at REAL DEFAULT 0,
    PRIMARY KEY (user_id, persona_id)
);

CREATE TABLE IF NOT EXISTS chat_summary (
    user_id TEXT NOT NULL,
    persona_id TEXT NOT NULL,
    summary TEXT DEFAULT '',
    message_count INTEGER DEFAULT 0,
    updated_at REAL DEFAULT 0,
    PRIMARY KEY (user_id, persona_id)
);

CREATE TABLE IF NOT EXISTS proactive_lock (
    user_id TEXT NOT NULL,
    persona_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    acquired_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    PRIMARY KEY (user_id, persona_id)
);

CREATE TABLE IF NOT EXISTS proactive_outbox (
    user_id TEXT NOT NULL,
    persona_id TEXT NOT NULL,
    tick_id TEXT NOT NULL,
    reply TEXT NOT NULL,
    modality TEXT NOT NULL DEFAULT '文字',
    monologue TEXT DEFAULT '',
    drive_id TEXT DEFAULT '',
    dedup_key TEXT DEFAULT '',
    created_at REAL NOT NULL,
    status TEXT DEFAULT 'pending',
    delivered_at REAL,
    PRIMARY KEY (user_id, persona_id, tick_id)
);
"""


def table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    """Return current column names for a SQLite table."""
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def _ensure_migration_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id TEXT PRIMARY KEY,
            applied_at REAL NOT NULL
        )
    """)


def _applied_migration_ids(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT id FROM schema_migrations").fetchall()
    return {row[0] for row in rows}


def _add_column_if_missing(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    if column_name in table_columns(conn, table_name):
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def _apply_initial_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(INITIAL_SCHEMA_SQL)


def _apply_genome_state_proactive_meta(conn: sqlite3.Connection) -> None:
    for column_name, column_definition in (
        ("state_version", "INTEGER DEFAULT 0"),
        ("last_active_at", "REAL DEFAULT 0"),
        ("interaction_cadence", "REAL DEFAULT 0"),
    ):
        _add_column_if_missing(
            conn,
            table_name="genome_state",
            column_name=column_name,
            column_definition=column_definition,
        )


SCHEMA_MIGRATIONS: tuple[SchemaMigration, ...] = (
    SchemaMigration("001_initial_state_schema", _apply_initial_schema),
    SchemaMigration("002_genome_state_proactive_meta", _apply_genome_state_proactive_meta),
)


def apply_state_schema_migrations(conn: sqlite3.Connection) -> None:
    """Apply all StateStore schema migrations exactly once per database."""
    _ensure_migration_table(conn)
    applied = _applied_migration_ids(conn)
    for migration in SCHEMA_MIGRATIONS:
        if migration.id in applied:
            continue
        with conn:
            migration.runner(conn)
            conn.execute(
                "INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)",
                (migration.id, time.time()),
            )
