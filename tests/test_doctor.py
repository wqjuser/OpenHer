"""Local doctor command tests."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "doctor.py"


def load_doctor_module():
    assert SCRIPT.exists(), "doctor script must exist"
    spec = importlib.util.spec_from_file_location("doctor", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_doctor_script_exposes_secret_safe_local_contracts():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "def build_doctor_report" in source
    assert "load_dotenv" in source
    assert "get_llm_config" in source
    assert "get_memory_config" in source
    assert "inventory_data_dir" in source
    assert "verify_backup_archive" in source
    assert "api_key_configured" in source
    assert "setup_hint" in source
    assert "--strict" in source
    assert "api_key\"" not in source


def test_doctor_report_marks_missing_required_llm_key_as_error(monkeypatch, tmp_path):
    doctor = load_doctor_module()
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("DEFAULT_PROVIDER", "deepseek")
    data_dir = tmp_path / "data"

    report = doctor.build_doctor_report(base_dir=ROOT, data_dir=data_dir, load_env=False)

    assert report["status"] == "error"
    assert report["checks"]["llm"]["status"] == "error"
    assert report["checks"]["llm"]["details"]["provider"] == "deepseek"
    assert report["checks"]["llm"]["details"]["api_key_configured"] is False
    assert report["checks"]["llm"]["details"]["missing_key_env"] == "DEEPSEEK_API_KEY or LLM_API_KEY"
    assert "DEEPSEEK_API_KEY or LLM_API_KEY" in report["checks"]["llm"]["setup_hint"]
    assert ".env" in report["checks"]["llm"]["setup_hint"]
    assert report["summary"]["error"] >= 1


def test_doctor_report_redacts_configured_api_key_values(monkeypatch, tmp_path):
    doctor = load_doctor_module()
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("DEFAULT_PROVIDER", "deepseek")
    monkeypatch.setenv("LLM_API_KEY", "super-secret-token")

    report = doctor.build_doctor_report(base_dir=ROOT, data_dir=tmp_path / "data", load_env=False)
    rendered = json.dumps(report, sort_keys=True)

    assert report["checks"]["llm"]["status"] == "ok"
    assert report["checks"]["llm"]["details"]["api_key_configured"] is True
    assert report["checks"]["llm"]["setup_hint"] == "No action needed."
    assert "super-secret-token" not in rendered
    assert "LLM_API_KEY" not in rendered


def test_doctor_report_shows_evermemos_cloud_default_without_leaking_key(monkeypatch, tmp_path):
    doctor = load_doctor_module()
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("DEFAULT_PROVIDER", "ollama")
    monkeypatch.setenv("EVERMEMOS_API_KEY", "memory-secret-token")

    report = doctor.build_doctor_report(base_dir=ROOT, data_dir=tmp_path / "data", load_env=False)
    rendered = json.dumps(report, sort_keys=True)

    assert report["checks"]["memory"]["status"] == "ok"
    assert report["checks"]["memory"]["details"]["api_key_configured"] is True
    assert report["checks"]["memory"]["details"]["base_url_configured"] is True
    assert report["checks"]["memory"]["details"]["uses_cloud_default"] is True
    assert report["checks"]["memory"]["setup_hint"] == "No action needed."
    assert "memory-secret-token" not in rendered


def test_doctor_report_includes_runtime_data_inventory_and_backup_verification(monkeypatch, tmp_path):
    doctor = load_doctor_module()
    lifecycle = _load_data_lifecycle_module()
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("DEFAULT_PROVIDER", "ollama")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    conn = sqlite3.connect(data_dir / "openher.db")
    conn.execute("CREATE TABLE genesis_seed (persona_id TEXT PRIMARY KEY, seeds TEXT NOT NULL)")
    conn.commit()
    conn.close()
    backup_path = lifecycle.backup_data_dir(
        data_dir=data_dir,
        backup_dir=tmp_path / "backups",
        timestamp="20260702T030405Z",
    )

    report = doctor.build_doctor_report(
        base_dir=ROOT,
        data_dir=data_dir,
        backup_path=backup_path,
        load_env=False,
    )

    assert report["status"] == "warn"
    assert report["checks"]["data"]["status"] == "ok"
    assert report["checks"]["data"]["details"]["exists"] is True
    assert report["checks"]["data"]["details"]["file_count"] == 1
    assert report["checks"]["backup"]["status"] == "ok"
    assert report["checks"]["backup"]["details"]["valid"] is True
    assert report["checks"]["backup"]["details"]["backup_path"] == str(backup_path)
    assert report["checks"]["backup"]["setup_hint"] == "No action needed."


def test_doctor_report_marks_invalid_backup_as_error(monkeypatch, tmp_path):
    doctor = load_doctor_module()
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("DEFAULT_PROVIDER", "ollama")
    bad_backup = tmp_path / "bad.zip"
    bad_backup.write_text("not a zip", encoding="utf-8")

    report = doctor.build_doctor_report(
        base_dir=ROOT,
        data_dir=tmp_path / "data",
        backup_path=bad_backup,
        load_env=False,
    )

    assert report["status"] == "error"
    assert report["checks"]["backup"]["status"] == "error"
    assert "not a zip" in " ".join(report["checks"]["backup"]["details"]["errors"])
    assert "make data-backup" in report["checks"]["backup"]["setup_hint"]


def test_doctor_cli_prints_json_without_live_provider_calls(tmp_path):
    env = os.environ.copy()
    for name in _PROVIDER_ENV_NAMES:
        env.pop(name, None)
    env["DEFAULT_PROVIDER"] = "ollama"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--json",
            "--no-env",
            "--data-dir",
            str(tmp_path / "data"),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["checks"]["llm"]["details"]["provider"] == "ollama"
    assert "super-secret-token" not in result.stdout
    assert result.stderr == ""


def test_doctor_report_includes_optional_and_backup_setup_hints(monkeypatch, tmp_path):
    doctor = load_doctor_module()
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("DEFAULT_PROVIDER", "ollama")

    report = doctor.build_doctor_report(base_dir=ROOT, data_dir=tmp_path / "data", load_env=False)

    assert report["status"] == "warn"
    assert "TTS_API_KEY" in report["checks"]["tts"]["setup_hint"]
    assert "optional" in report["checks"]["tts"]["setup_hint"]
    assert "IMAGE_API_KEY" in report["checks"]["image"]["setup_hint"]
    assert "optional" in report["checks"]["image"]["setup_hint"]
    assert "OPENHER_DATA_DIR" in report["checks"]["data"]["setup_hint"]
    assert "make data-backup" in report["checks"]["backup"]["setup_hint"]


def test_doctor_pretty_output_includes_setup_hints(tmp_path):
    env = os.environ.copy()
    for name in _PROVIDER_ENV_NAMES:
        env.pop(name, None)
    env["DEFAULT_PROVIDER"] = "ollama"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--pretty",
            "--no-env",
            "--data-dir",
            str(tmp_path / "data"),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0
    assert "hint:" in result.stdout
    assert "make data-backup" in result.stdout
    assert result.stderr == ""


def test_doctor_strict_exits_nonzero_on_warning_only_report(tmp_path):
    env = os.environ.copy()
    for name in _PROVIDER_ENV_NAMES:
        env.pop(name, None)
    env["DEFAULT_PROVIDER"] = "ollama"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--json",
            "--strict",
            "--no-env",
            "--data-dir",
            str(tmp_path / "data"),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["status"] == "warn"
    assert report["summary"]["error"] == 0
    assert report["summary"]["warn"] > 0
    assert result.stderr == ""


def _load_data_lifecycle_module():
    script = ROOT / "scripts" / "data_lifecycle.py"
    spec = importlib.util.spec_from_file_location("data_lifecycle", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PROVIDER_ENV_NAMES = (
    "DEFAULT_PROVIDER",
    "DEFAULT_MODEL",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DASHSCOPE_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "MINIMAX_LLM_API_KEY",
    "MINIMAX_API_KEY",
    "MOONSHOT_API_KEY",
    "STEPFUN_API_KEY",
    "TTS_API_KEY",
    "IMAGE_API_KEY",
    "EVERMEMOS_API_KEY",
    "EVERMEMOS_BASE_URL",
    "MEMORY_API_KEY",
    "MEMORY_BASE_URL",
)


def _clear_provider_env(monkeypatch):
    for name in _PROVIDER_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
