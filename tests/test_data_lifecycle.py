"""Runtime data lifecycle command tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "data_lifecycle.py"


def load_data_lifecycle_module():
    assert SCRIPT.exists(), "data lifecycle script must exist"
    spec = importlib.util.spec_from_file_location("data_lifecycle", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_data_lifecycle_script_exposes_backup_reset_and_inventory_contracts():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "OPENHER_DATA_DIR" in source
    assert "def resolve_data_dir" in source
    assert "def inventory_data_dir" in source
    assert "def backup_data_dir" in source
    assert "def verify_backup_archive" in source
    assert "def restore_data_backup" in source
    assert "def reset_runtime_data" in source
    assert "genesis_seed" in source
    assert "genome_state" in source
    assert "proactive_outbox" in source
    assert "zipfile.ZipFile" in source


def test_resolve_data_dir_uses_env_override(monkeypatch, tmp_path):
    lifecycle = load_data_lifecycle_module()

    monkeypatch.delenv("OPENHER_DATA_DIR", raising=False)
    assert lifecycle.resolve_data_dir(base_dir=tmp_path) == tmp_path / ".data"

    monkeypatch.setenv("OPENHER_DATA_DIR", "runtime-data")
    assert lifecycle.resolve_data_dir(base_dir=tmp_path) == tmp_path / "runtime-data"

    absolute = tmp_path / "absolute-data"
    monkeypatch.setenv("OPENHER_DATA_DIR", str(absolute))
    assert lifecycle.resolve_data_dir(base_dir=tmp_path) == absolute


def test_backup_data_dir_creates_zip_manifest_and_files(tmp_path):
    lifecycle = load_data_lifecycle_module()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "openher.db").write_bytes(b"openher")
    (data_dir / "chat.db").write_bytes(b"chat")
    (data_dir / "genome").mkdir()
    (data_dir / "genome" / "state.json").write_text('{"ok": true}', encoding="utf-8")

    backup_path = lifecycle.backup_data_dir(
        data_dir=data_dir,
        backup_dir=tmp_path / "backups",
        timestamp="20260702T010203Z",
    )

    assert backup_path.name == "openher-data-20260702T010203Z.zip"
    with zipfile.ZipFile(backup_path) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "openher.db" in names
        assert "chat.db" in names
        assert "genome/state.json" in names
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))

    assert manifest["schema_version"] == 1
    assert manifest["data_dir"] == str(data_dir)
    assert {entry["path"] for entry in manifest["files"]} == {
        "openher.db",
        "chat.db",
        "genome/state.json",
    }


def test_verify_backup_archive_accepts_manifested_files(tmp_path):
    lifecycle = load_data_lifecycle_module()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "openher.db").write_bytes(b"openher")
    (data_dir / "chat.db").write_bytes(b"chat")

    backup_path = lifecycle.backup_data_dir(
        data_dir=data_dir,
        backup_dir=tmp_path / "backups",
        timestamp="20260702T020304Z",
    )

    result = lifecycle.verify_backup_archive(backup_path)

    assert result["valid"] is True
    assert result["errors"] == []
    assert result["manifest"]["schema_version"] == 1
    assert {entry["path"] for entry in result["manifest"]["files"]} == {"openher.db", "chat.db"}


def test_inventory_data_dir_reports_corrupt_openher_db_without_raising(tmp_path):
    lifecycle = load_data_lifecycle_module()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "openher.db").write_bytes(b"not sqlite")

    inventory = lifecycle.inventory_data_dir(data_dir)

    sqlite_inventory = inventory["sqlite"]["openher.db"]
    assert inventory["exists"] is True
    assert sqlite_inventory["error"]
    assert "file is not a database" in sqlite_inventory["error"]


@pytest.mark.parametrize("unsafe_path", ["../evil.txt", "/evil.txt", "C:/evil.txt", "folder\\evil.txt"])
def test_verify_backup_archive_rejects_unsafe_manifest_paths(tmp_path, unsafe_path):
    lifecycle = load_data_lifecycle_module()
    backup_path = tmp_path / "unsafe.zip"
    manifest = {
        "schema_version": 1,
        "created_at": "20260702T020304Z",
        "data_dir": str(tmp_path / "data"),
        "files": [{"path": unsafe_path, "size": 4}],
    }
    with zipfile.ZipFile(backup_path, mode="w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr(unsafe_path, b"evil")

    result = lifecycle.verify_backup_archive(backup_path)

    assert result["valid"] is False
    assert any("unsafe path" in error for error in result["errors"])


def test_restore_data_backup_refuses_non_empty_target_without_overwrite(tmp_path):
    lifecycle = load_data_lifecycle_module()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "openher.db").write_bytes(b"openher")
    backup_path = lifecycle.backup_data_dir(
        data_dir=data_dir,
        backup_dir=tmp_path / "backups",
        timestamp="20260702T020304Z",
    )
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / "existing.txt").write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError, match="not empty"):
        lifecycle.restore_data_backup(backup_path, target_dir)


def test_restore_data_backup_restores_files_and_preserves_pre_restore_backup(tmp_path):
    lifecycle = load_data_lifecycle_module()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "openher.db").write_bytes(b"openher")
    (data_dir / "chat.db").write_bytes(b"chat")
    (data_dir / "genome").mkdir()
    (data_dir / "genome" / "state.json").write_text('{"ok": true}', encoding="utf-8")
    backup_path = lifecycle.backup_data_dir(
        data_dir=data_dir,
        backup_dir=tmp_path / "backups",
        timestamp="20260702T020304Z",
    )
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / "stale.txt").write_text("stale", encoding="utf-8")
    (target_dir / "openher.db").write_bytes(b"old-openher")

    result = lifecycle.restore_data_backup(
        backup_path=backup_path,
        data_dir=target_dir,
        overwrite=True,
        backup_dir=tmp_path / "pre-restore-backups",
    )

    assert sorted(result["restored_files"]) == ["chat.db", "genome/state.json", "openher.db"]
    assert sorted(result["deleted_files"]) == ["openher.db", "stale.txt"]
    assert (target_dir / "openher.db").read_bytes() == b"openher"
    assert (target_dir / "chat.db").read_bytes() == b"chat"
    assert (target_dir / "genome" / "state.json").read_text(encoding="utf-8") == '{"ok": true}'
    assert not (target_dir / "stale.txt").exists()

    pre_restore_backup = Path(result["pre_restore_backup_path"])
    assert pre_restore_backup.exists()
    with zipfile.ZipFile(pre_restore_backup) as archive:
        assert "stale.txt" in archive.namelist()


def test_reset_runtime_data_preserves_genesis_seed_and_clears_runtime_tables(tmp_path):
    lifecycle = load_data_lifecycle_module()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for name in ("chat.db", "memory.db", "task.db", "server.log"):
        (data_dir / name).write_text(name, encoding="utf-8")
    openher_db = data_dir / "openher.db"
    _create_openher_db(openher_db)

    summary = lifecycle.reset_runtime_data(data_dir=data_dir)

    assert sorted(summary["deleted_files"]) == ["chat.db", "memory.db", "server.log", "task.db"]
    for name in ("chat.db", "memory.db", "task.db", "server.log"):
        assert not (data_dir / name).exists()

    conn = sqlite3.connect(openher_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM genesis_seed").fetchone()[0] == 1
        for table in (
            "style_memory",
            "genome_state",
            "chat_summary",
            "proactive_lock",
            "proactive_outbox",
        ):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    finally:
        conn.close()


def test_reset_runtime_data_reports_corrupt_openher_db_without_raising(tmp_path):
    lifecycle = load_data_lifecycle_module()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for name in ("chat.db", "memory.db", "task.db", "server.log"):
        (data_dir / name).write_text(name, encoding="utf-8")
    openher_db = data_dir / "openher.db"
    openher_db.write_bytes(b"not sqlite")

    summary = lifecycle.reset_runtime_data(data_dir=data_dir)

    assert sorted(summary["deleted_files"]) == ["chat.db", "memory.db", "server.log", "task.db"]
    assert openher_db.read_bytes() == b"not sqlite"
    assert summary["cleared_tables"] == []
    assert summary["genesis_seed_count"] == 0
    assert summary["errors"]
    assert "SQLite reset failed for openher.db" in summary["errors"][0]


def test_data_lifecycle_reset_cli_reports_corrupt_openher_db_as_json(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "openher.db").write_bytes(b"not sqlite")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--data-dir",
            str(data_dir),
            "reset",
            "--no-backup",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["status"] == "error"
    assert payload["reset"]["errors"]
    assert "SQLite reset failed for openher.db" in payload["reset"]["errors"][0]
    assert result.stderr == ""


def test_reset_data_legacy_entrypoint_delegates_to_data_lifecycle_module():
    source = (ROOT / "scripts" / "reset_data.py").read_text(encoding="utf-8")

    assert "from scripts.data_lifecycle import" in source
    assert "resolve_data_dir" in source
    assert "reset_runtime_data" in source
    assert 'summary.get("errors", [])' in source
    assert "raise SystemExit(1)" in source


def _create_openher_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript("""
            CREATE TABLE genesis_seed (
                persona_id TEXT PRIMARY KEY,
                seeds TEXT NOT NULL
            );
            INSERT INTO genesis_seed (persona_id, seeds) VALUES ('iris', '[]');

            CREATE TABLE style_memory (id INTEGER PRIMARY KEY, content TEXT);
            INSERT INTO style_memory (content) VALUES ('style');

            CREATE TABLE genome_state (
                user_id TEXT,
                persona_id TEXT,
                agent_data TEXT DEFAULT '{}',
                metabolism_data TEXT DEFAULT '{}'
            );
            INSERT INTO genome_state (user_id, persona_id) VALUES ('u', 'iris');

            CREATE TABLE chat_summary (
                user_id TEXT,
                persona_id TEXT,
                summary TEXT
            );
            INSERT INTO chat_summary (user_id, persona_id, summary) VALUES ('u', 'iris', 'summary');

            CREATE TABLE proactive_lock (
                user_id TEXT,
                persona_id TEXT,
                owner_id TEXT,
                acquired_at REAL,
                expires_at REAL
            );
            INSERT INTO proactive_lock VALUES ('u', 'iris', 'owner', 1, 2);

            CREATE TABLE proactive_outbox (
                user_id TEXT,
                persona_id TEXT,
                tick_id TEXT,
                reply TEXT,
                modality TEXT,
                created_at REAL,
                status TEXT
            );
            INSERT INTO proactive_outbox VALUES ('u', 'iris', 'tick', 'hi', '文字', 1, 'pending');
        """)
        conn.commit()
    finally:
        conn.close()
