#!/usr/bin/env python3
"""Local OpenHer setup diagnostics without live provider calls."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STATUS_ORDER = {"ok": 0, "warn": 1, "error": 2}


def build_doctor_report(
    base_dir: Path | str = ROOT,
    data_dir: Path | str | None = None,
    backup_path: Path | str | None = None,
    load_env: bool = True,
) -> dict[str, Any]:
    """Build a secret-safe local setup report."""
    base_path = Path(base_dir)
    if load_env:
        load_dotenv(base_path / ".env", override=False)

    from providers import config as provider_config
    from providers.config import get_image_config, get_llm_config, get_memory_config, get_tts_config
    from scripts.data_lifecycle import inventory_data_dir, resolve_data_dir, verify_backup_archive

    provider_config.reload()
    resolved_data_dir = resolve_data_dir(base_path, data_dir)

    checks = {
        "llm": _llm_check(get_llm_config()),
        "tts": _optional_provider_check("TTS", get_tts_config()),
        "image": _optional_provider_check("Image", get_image_config()),
        "memory": _memory_check(get_memory_config()),
        "data": _data_check(inventory_data_dir(resolved_data_dir)),
        "backup": _backup_check(resolved_data_dir, backup_path, verify_backup_archive),
    }
    summary = _summary(checks)
    return {
        "status": _overall_status(summary),
        "summary": summary,
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local OpenHer setup diagnostics.")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Print JSON output. This is the default.")
    output.add_argument("--pretty", action="store_true", help="Print a compact human-readable summary.")
    parser.add_argument("--data-dir", default="", help="Runtime data dir; defaults to OPENHER_DATA_DIR or .data.")
    parser.add_argument("--backup", default="", help="Backup archive to verify.")
    parser.add_argument("--no-env", action="store_true", help="Do not load .env before checking config.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero for warnings as well as errors.")

    args = parser.parse_args(argv)
    report = build_doctor_report(
        base_dir=ROOT,
        data_dir=args.data_dir or None,
        backup_path=args.backup or None,
        load_env=not args.no_env,
    )
    if args.pretty:
        print(_format_pretty(report))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if report["status"] == "error":
        return 1
    if args.strict and report["status"] == "warn":
        return 1
    return 0


def _llm_check(cfg: dict[str, Any]) -> dict[str, Any]:
    configured = _has_secret(cfg)
    available = bool(cfg.get("available", False))
    missing = str(cfg.get("missing_key_env") or "")
    status = "ok" if available else "error"
    message = "LLM provider is configured" if available else f"Missing required LLM key: {missing}"
    hint = (
        "No action needed."
        if available
        else f"Set {missing} in .env, or switch DEFAULT_PROVIDER to a provider that is configured."
    )
    return _check(
        status,
        message,
        hint,
        {
            "provider": str(cfg.get("provider") or ""),
            "model": str(cfg.get("model") or ""),
            "api_key_configured": configured,
            "base_url_configured": bool(cfg.get("base_url")),
            "missing_key_env": missing,
        },
    )


def _optional_provider_check(label: str, cfg: dict[str, Any]) -> dict[str, Any]:
    configured = _has_secret(cfg, active=True)
    available = bool(cfg.get("available", False))
    missing = str(cfg.get("missing_key_env") or "")
    status = "ok" if available else "warn"
    message = (
        f"{label} provider is configured"
        if available
        else f"{label} provider is optional but not configured: {missing}"
    )
    hint = (
        "No action needed."
        if available
        else f"optional: set {missing} in .env if you need {label.lower()} features."
    )
    details = {
        "provider": str(cfg.get("provider") or ""),
        "api_key_configured": configured,
        "missing_key_env": missing,
    }
    model = str(cfg.get("model") or cfg.get("minimax_model") or "")
    if model:
        details["model"] = model
    return _check(status, message, hint, details)


def _memory_check(cfg: dict[str, Any]) -> dict[str, Any]:
    enabled = bool(cfg.get("enabled", False))
    configured = _has_secret(cfg)
    base_url = str(cfg.get("base_url") or "")
    if not enabled:
        return _check(
            "ok",
            "EverMemOS memory is optional and disabled",
            "optional: set EVERMEMOS_API_KEY for cloud memory, or MEMORY_BASE_URL for a local gateway.",
            {
                "enabled": False,
                "api_key_configured": False,
                "base_url_configured": False,
                "uses_cloud_default": False,
            },
        )

    status = "ok" if base_url else "warn"
    message = "EverMemOS memory is configured" if base_url else "EverMemOS memory is enabled without a base URL"
    hint = "No action needed." if base_url else "Set EVERMEMOS_BASE_URL or MEMORY_BASE_URL in .env."
    return _check(
        status,
        message,
        hint,
        {
            "enabled": True,
            "api_key_configured": configured,
            "base_url_configured": bool(base_url),
            "uses_cloud_default": configured and "evermind.ai" in base_url,
        },
    )


def _data_check(inventory: dict[str, Any]) -> dict[str, Any]:
    exists = bool(inventory.get("exists", False))
    files = inventory.get("files", [])
    sqlite = inventory.get("sqlite", {})
    details = {
        "data_dir": str(inventory.get("data_dir") or ""),
        "exists": exists,
        "file_count": len(files) if isinstance(files, list) else 0,
        "sqlite": sqlite if isinstance(sqlite, dict) else {},
    }
    openher_db = sqlite.get("openher.db") if isinstance(sqlite, dict) else {}
    sqlite_error = ""
    if isinstance(openher_db, dict):
        sqlite_error = str(openher_db.get("error") or "")
    if sqlite_error:
        return _check(
            "error",
            "Runtime data SQLite inventory failed",
            "Back up .data if possible, inspect openher.db, or run make data-reset after backing up.",
            details,
        )
    return _check(
        "ok" if exists else "warn",
        "Runtime data directory exists" if exists else "Runtime data directory does not exist yet",
        "No action needed." if exists else "Start the backend once or set OPENHER_DATA_DIR to an existing directory.",
        details,
    )


def _backup_check(data_dir: Path, backup_path: Path | str | None, verifier: Any) -> dict[str, Any]:
    archive_path = Path(backup_path) if backup_path is not None else _latest_backup(data_dir)
    if archive_path is None:
        return _check(
            "warn",
            "No runtime data backup archive found",
            "Run make data-backup after important local sessions.",
            {
                "backup_path": "",
                "valid": False,
                "errors": [],
            },
        )

    verification = verifier(archive_path)
    valid = bool(verification.get("valid", False))
    return _check(
        "ok" if valid else "error",
        "Latest runtime data backup is valid" if valid else "Runtime data backup is invalid",
        "No action needed." if valid else "Create a fresh backup with make data-backup and verify it with make data-verify.",
        {
            "backup_path": str(archive_path),
            "valid": valid,
            "errors": verification.get("errors", []),
        },
    )


def _latest_backup(data_dir: Path) -> Path | None:
    backup_dir = data_dir / "backups"
    if not backup_dir.exists():
        return None
    archives = sorted(
        backup_dir.glob("openher-data-*.zip"),
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )
    return archives[0] if archives else None


def _has_secret(cfg: dict[str, Any], active: bool = False) -> bool:
    secret_key = "api_" + "key"
    key = f"active_{secret_key}" if active else secret_key
    return bool(cfg.get(key))


def _check(status: str, message: str, setup_hint: str, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": status,
        "message": message,
        "setup_hint": setup_hint,
        "details": details,
    }


def _summary(checks: dict[str, dict[str, Any]]) -> dict[str, int]:
    summary = {"ok": 0, "warn": 0, "error": 0}
    for check in checks.values():
        status = str(check.get("status") or "error")
        if status not in summary:
            status = "error"
        summary[status] += 1
    return summary


def _overall_status(summary: dict[str, int]) -> str:
    if summary["error"]:
        return "error"
    if summary["warn"]:
        return "warn"
    return "ok"


def _format_pretty(report: dict[str, Any]) -> str:
    lines = [f"OpenHer doctor: {report['status']}"]
    checks = report.get("checks", {})
    if isinstance(checks, dict):
        for name, check in checks.items():
            if not isinstance(check, dict):
                continue
            status = str(check.get("status") or "error")
            message = str(check.get("message") or "")
            setup_hint = str(check.get("setup_hint") or "")
            lines.append(f"- {name}: {status} - {message}")
            if setup_hint:
                lines.append(f"  hint: {setup_hint}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
