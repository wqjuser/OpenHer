#!/usr/bin/env python3
"""OpenHer runtime data inventory, backup, and reset utilities."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DB_FILES = ("chat.db", "memory.db", "task.db")
RUNTIME_LOG_FILES = ("server.log",)
OPENHER_RUNTIME_TABLES = (
    "style_memory",
    "genome_state",
    "chat_summary",
    "proactive_lock",
    "proactive_outbox",
)


def resolve_data_dir(
    base_dir: Path | str = ROOT,
    override: str | Path | None = None,
) -> Path:
    """Resolve the runtime data directory using OPENHER_DATA_DIR semantics."""
    base_path = Path(base_dir)
    configured = str(override or os.getenv("OPENHER_DATA_DIR", "")).strip()
    if not configured:
        return base_path / ".data"
    path = Path(configured)
    return path if path.is_absolute() else base_path / path


def inventory_data_dir(data_dir: Path | str) -> dict[str, Any]:
    """Return a compact inventory of runtime data files and known SQLite tables."""
    root = Path(data_dir)
    files = [
        {
            "path": _relative_posix(path, root),
            "size": path.stat().st_size,
        }
        for path in _iter_files(root)
    ]
    inventory: dict[str, Any] = {
        "data_dir": str(root),
        "exists": root.exists(),
        "files": files,
        "sqlite": {},
    }
    openher_db = root / "openher.db"
    if openher_db.exists():
        inventory["sqlite"]["openher.db"] = _sqlite_table_counts(
            openher_db,
            ("genesis_seed", *OPENHER_RUNTIME_TABLES),
        )
    return inventory


def backup_data_dir(
    data_dir: Path | str,
    backup_dir: Path | str | None = None,
    timestamp: str | None = None,
) -> Path:
    """Create a zip backup of runtime data with a small manifest."""
    root = Path(data_dir)
    stamp = timestamp or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    destination_dir = Path(backup_dir) if backup_dir is not None else root / "backups"
    destination_dir.mkdir(parents=True, exist_ok=True)
    backup_path = destination_dir / f"openher-data-{stamp}.zip"

    files = [
        path
        for path in _iter_files(root)
        if not _is_relative_to(path, destination_dir)
    ]
    manifest = {
        "schema_version": 1,
        "created_at": stamp,
        "data_dir": str(root),
        "files": [
            {
                "path": _relative_posix(path, root),
                "size": path.stat().st_size,
            }
            for path in files
        ],
    }

    with zipfile.ZipFile(backup_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for path in files:
            archive.write(path, _relative_posix(path, root))

    return backup_path


def reset_runtime_data(data_dir: Path | str) -> dict[str, Any]:
    """Remove user runtime data while preserving genesis seeds in openher.db."""
    root = Path(data_dir)
    summary: dict[str, Any] = {
        "data_dir": str(root),
        "deleted_files": [],
        "missing_files": [],
        "cleared_tables": [],
        "genesis_seed_count": 0,
    }

    for filename in (*RUNTIME_DB_FILES, *RUNTIME_LOG_FILES):
        path = root / filename
        if path.exists():
            path.unlink()
            summary["deleted_files"].append(filename)
        else:
            summary["missing_files"].append(filename)

    openher_db = root / "openher.db"
    if openher_db.exists():
        conn = sqlite3.connect(openher_db)
        try:
            for table in OPENHER_RUNTIME_TABLES:
                if _table_exists(conn, table):
                    conn.execute(f"DELETE FROM {table}")
                    summary["cleared_tables"].append(table)
            conn.commit()
            if _table_exists(conn, "genesis_seed"):
                row = conn.execute("SELECT COUNT(*) FROM genesis_seed").fetchone()
                summary["genesis_seed_count"] = int(row[0]) if row else 0
        finally:
            conn.close()

    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage OpenHer runtime data.")
    parser.add_argument("--data-dir", default="", help="Runtime data dir; defaults to OPENHER_DATA_DIR or .data.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("inventory", help="Print runtime data inventory as JSON.")

    backup_parser = subparsers.add_parser("backup", help="Create a zip backup of runtime data.")
    backup_parser.add_argument("--backup-dir", default="", help="Backup destination; defaults to <data-dir>/backups.")

    reset_parser = subparsers.add_parser("reset", help="Back up and clear runtime data while preserving seeds.")
    reset_parser.add_argument("--backup-dir", default="", help="Backup destination; defaults to <data-dir>/backups.")
    reset_parser.add_argument("--no-backup", action="store_true", help="Skip the pre-reset backup.")

    args = parser.parse_args(argv)
    data_dir = resolve_data_dir(ROOT, args.data_dir or None)

    if args.command == "inventory":
        _print_json(inventory_data_dir(data_dir))
        return 0

    if args.command == "backup":
        backup_path = backup_data_dir(
            data_dir,
            backup_dir=Path(args.backup_dir) if args.backup_dir else None,
        )
        _print_json({"status": "ok", "backup_path": str(backup_path)})
        return 0

    if args.command == "reset":
        result: dict[str, Any] = {"status": "ok"}
        if not args.no_backup:
            backup_path = backup_data_dir(
                data_dir,
                backup_dir=Path(args.backup_dir) if args.backup_dir else None,
            )
            result["backup_path"] = str(backup_path)
        result["reset"] = reset_runtime_data(data_dir)
        _print_json(result)
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


def _iter_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def _sqlite_table_counts(db_path: Path, tables: tuple[str, ...]) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    try:
        counts: dict[str, int] = {}
        for table in tables:
            if _table_exists(conn, table):
                row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                counts[table] = int(row[0]) if row else 0
        return counts
    finally:
        conn.close()


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
