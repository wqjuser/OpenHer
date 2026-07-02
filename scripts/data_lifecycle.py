#!/usr/bin/env python3
"""OpenHer runtime data inventory, backup, and reset utilities."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import shutil
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


def verify_backup_archive(backup_path: Path | str) -> dict[str, Any]:
    """Validate a runtime data backup archive without extracting it."""
    archive_path = Path(backup_path)
    result: dict[str, Any] = {
        "backup_path": str(archive_path),
        "valid": False,
        "errors": [],
        "entries": [],
        "manifest": None,
    }
    errors: list[str] = result["errors"]

    if not archive_path.exists():
        errors.append("backup archive does not exist")
        return result

    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = {name for name in archive.namelist() if not name.endswith("/")}
            result["entries"] = sorted(names)
            if "manifest.json" not in names:
                errors.append("manifest.json is missing")
                return result

            for name in names:
                if name != "manifest.json" and not _is_safe_archive_path(name):
                    errors.append(f"unsafe path in archive: {name}")

            try:
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                errors.append(f"manifest.json is invalid: {exc}")
                return result

            if not isinstance(manifest, dict):
                errors.append("manifest.json must contain an object")
                return result
            result["manifest"] = manifest

            if manifest.get("schema_version") != 1:
                errors.append("unsupported manifest schema_version")

            files = manifest.get("files")
            if not isinstance(files, list):
                errors.append("manifest files must be a list")
                files = []

            for index, entry in enumerate(files):
                if not isinstance(entry, dict):
                    errors.append(f"manifest files[{index}] must be an object")
                    continue
                rel_path = entry.get("path")
                size = entry.get("size")
                if not isinstance(rel_path, str) or not rel_path:
                    errors.append(f"manifest files[{index}].path must be a non-empty string")
                    continue
                if not _is_safe_archive_path(rel_path):
                    errors.append(f"unsafe path in manifest: {rel_path}")
                    continue
                if rel_path not in names:
                    errors.append(f"manifest entry missing from archive: {rel_path}")
                    continue
                if not isinstance(size, int) or size < 0:
                    errors.append(f"manifest files[{index}].size must be a non-negative integer")
                    continue
                actual_size = archive.getinfo(rel_path).file_size
                if actual_size != size:
                    errors.append(
                        f"size mismatch for {rel_path}: manifest={size} archive={actual_size}"
                    )
    except zipfile.BadZipFile as exc:
        errors.append(f"backup archive is not a zip file: {exc}")

    result["valid"] = not errors
    return result


def restore_data_backup(
    backup_path: Path | str,
    data_dir: Path | str,
    overwrite: bool = False,
    backup_existing: bool = True,
    backup_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Restore a verified runtime data backup into a data directory."""
    archive_path = Path(backup_path)
    root = Path(data_dir)
    verification = verify_backup_archive(archive_path)
    if not verification["valid"]:
        raise ValueError("invalid backup archive: " + "; ".join(verification["errors"]))

    existing_files = _iter_files(root)
    if existing_files and not overwrite:
        raise FileExistsError(f"{root} is not empty; pass overwrite=True to replace it")

    pre_restore_backup_path: Path | None = None
    if existing_files and overwrite and backup_existing:
        pre_restore_backup_path = backup_data_dir(root, backup_dir=backup_dir)

    root.mkdir(parents=True, exist_ok=True)
    deleted_files: list[str] = []
    if overwrite:
        protected_paths = [archive_path]
        if pre_restore_backup_path is not None:
            protected_paths.append(pre_restore_backup_path)
        deleted_files = _clear_data_dir(root, protected_paths)

    manifest = verification["manifest"]
    files = manifest["files"] if isinstance(manifest, dict) else []
    restored_files: list[str] = []
    with zipfile.ZipFile(archive_path) as archive:
        for entry in files:
            rel_path = entry["path"]
            destination = root / rel_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(rel_path) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
            restored_files.append(rel_path)

    return {
        "backup_path": str(archive_path),
        "data_dir": str(root),
        "pre_restore_backup_path": str(pre_restore_backup_path) if pre_restore_backup_path else "",
        "deleted_files": sorted(deleted_files),
        "restored_files": sorted(restored_files),
    }


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

    verify_parser = subparsers.add_parser("verify", help="Verify a runtime data backup archive.")
    verify_parser.add_argument("backup_path", help="Path to an openher-data-*.zip backup.")

    restore_parser = subparsers.add_parser("restore", help="Restore a runtime data backup archive.")
    restore_parser.add_argument("backup_path", help="Path to an openher-data-*.zip backup.")
    restore_parser.add_argument("--backup-dir", default="", help="Pre-restore backup destination.")
    restore_parser.add_argument("--overwrite", action="store_true", help="Replace an existing non-empty data dir.")
    restore_parser.add_argument("--no-backup", action="store_true", help="Skip the pre-restore backup.")

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

    if args.command == "verify":
        result = verify_backup_archive(Path(args.backup_path))
        result["status"] = "ok" if result["valid"] else "error"
        _print_json(result)
        return 0 if result["valid"] else 1

    if args.command == "restore":
        try:
            restore_result = restore_data_backup(
                backup_path=Path(args.backup_path),
                data_dir=data_dir,
                overwrite=args.overwrite,
                backup_existing=not args.no_backup,
                backup_dir=Path(args.backup_dir) if args.backup_dir else None,
            )
        except (FileExistsError, ValueError) as exc:
            _print_json({"status": "error", "error": str(exc)})
            return 1
        _print_json({"status": "ok", "restore": restore_result})
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


def _clear_data_dir(root: Path, protected_paths: list[Path]) -> list[str]:
    protected = {
        path.resolve()
        for path in protected_paths
        if path.exists()
    }
    deleted: list[str] = []
    for path in _iter_files(root):
        if path.resolve() in protected:
            continue
        deleted.append(_relative_posix(path, root))
        path.unlink()
    for directory in sorted((path for path in root.rglob("*") if path.is_dir()), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass
    return sorted(deleted)


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


def _is_safe_archive_path(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        bool(value)
        and "\\" not in value
        and ":" not in value
        and not path.is_absolute()
        and ".." not in path.parts
    )


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
