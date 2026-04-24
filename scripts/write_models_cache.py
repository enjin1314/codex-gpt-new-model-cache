#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = SKILL_DIR / "assets" / "models_cache.template.json"
LATEST_RELEASE_URL = "https://api.github.com/repos/openai/codex/releases/latest"


def iso_utc_after_30_days() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        + timedelta(days=30)
    ).isoformat().replace("+00:00", "Z")


def existing_cache_version(cache_path: Path) -> str | None:
    if not cache_path.exists():
        return None
    try:
        with cache_path.open("r", encoding="utf-8") as cache_file:
            value = json.load(cache_file).get("client_version")
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, str) and value else None


def version_json_version(codex_home: Path) -> str | None:
    version_path = codex_home / "version.json"
    if not version_path.exists():
        return None
    try:
        with version_path.open("r", encoding="utf-8") as version_file:
            value = json.load(version_file).get("latest_version")
    except (OSError, json.JSONDecodeError):
        return None
    return normalize_version(value)


def latest_session_version(codex_home: Path) -> str | None:
    for version in (
        latest_sqlite_thread_version(codex_home),
        latest_jsonl_session_version(codex_home),
    ):
        if version:
            return version
    return None


def latest_sqlite_thread_version(codex_home: Path) -> str | None:
    sqlite_home = Path(os.environ.get("CODEX_SQLITE_HOME", codex_home)).expanduser()
    state_path = sqlite_home / "state_5.sqlite"
    if not state_path.exists():
        return None
    try:
        connection = sqlite3.connect(f"file:{state_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        row = connection.execute(
            """
            SELECT cli_version
            FROM threads
            WHERE cli_version IS NOT NULL AND cli_version != ''
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        connection.close()
    if not row:
        return None
    return normalize_version(row[0])


def latest_jsonl_session_version(codex_home: Path) -> str | None:
    sessions_dir = codex_home / "sessions"
    if not sessions_dir.exists():
        return None
    try:
        session_files = sorted(
            sessions_dir.rglob("*.jsonl"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return None

    for session_file in session_files[:20]:
        try:
            with session_file.open("r", encoding="utf-8") as handle:
                first_line = handle.readline()
        except OSError:
            continue
        try:
            session_line = json.loads(first_line)
        except json.JSONDecodeError:
            continue
        if session_line.get("type") == "session_meta":
            meta = session_line.get("payload", {})
        else:
            item = session_line.get("item", {})
            if item.get("type") != "session_meta":
                continue
            meta = item.get("meta", {})
        if not isinstance(meta, dict):
            continue
        if version := normalize_version(meta.get("cli_version")):
            return version
    return None


def normalize_version(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    version = value.strip()
    if version.startswith("codex-cli "):
        version = version.split(maxsplit=1)[1]
    if version.startswith("rust-v"):
        version = version.removeprefix("rust-v")
    version = version.split("-", maxsplit=1)[0]
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    return version


def codex_binary_candidates() -> list[Path]:
    candidates: list[Path] = []
    for env_name in ("CODEX_BINARY_PATH", "CODEX_BINARY"):
        if value := os.environ.get(env_name):
            candidates.append(Path(value).expanduser())

    if sys.platform == "darwin":
        candidates.append(Path("/Applications/Codex.app/Contents/Resources/codex"))
    elif sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            roots = [
                Path(local_app_data) / "Programs",
                Path(local_app_data) / "Microsoft" / "WindowsApps",
            ]
            for root in roots:
                if root.exists():
                    candidates.extend(root.rglob("codex.exe"))

    if path_codex := shutil.which("codex"):
        candidates.append(Path(path_codex))

    seen: set[Path] = set()
    unique_candidates: list[Path] = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        if resolved not in seen:
            seen.add(resolved)
            unique_candidates.append(candidate)
    return unique_candidates


def codex_binary_version() -> str | None:
    for candidate in codex_binary_candidates():
        if not candidate.exists():
            continue
        try:
            result = subprocess.run(
                [str(candidate), "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode != 0:
            continue
        for token in result.stdout.strip().split():
            if version := normalize_version(token):
                return version
    return None


def latest_github_release_version() -> str | None:
    request = urllib.request.Request(
        LATEST_RELEASE_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "codex-gpt-new-model-cache-skill",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None

    tag_name = payload.get("tag_name")
    return normalize_version(tag_name)


def main() -> None:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    cache_path = codex_home / "models_cache.json"
    backup_path = codex_home / "models_cache.json.bak"

    with TEMPLATE_PATH.open("r", encoding="utf-8") as template_file:
        cache = json.load(template_file)

    cache["fetched_at"] = iso_utc_after_30_days()
    cache["client_version"] = (
        codex_binary_version()
        or latest_session_version(codex_home)
        or version_json_version(codex_home)
        or latest_github_release_version()
        or existing_cache_version(cache_path)
        or os.environ.get("CODEX_CLIENT_VERSION")
        or cache.get("client_version")
    )

    codex_home.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        shutil.copy2(cache_path, backup_path)

    tmp_path = cache_path.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as cache_file:
        json.dump(cache, cache_file, ensure_ascii=False, indent=2)
        cache_file.write("\n")
    tmp_path.replace(cache_path)

    model_slugs = ", ".join(model["slug"] for model in cache.get("models", []))
    print(f"Wrote {cache_path}")
    print(f"fetched_at: {cache['fetched_at']}")
    print(f"client_version: {cache['client_version']}")
    print(f"models: {model_slugs}")


if __name__ == "__main__":
    main()
