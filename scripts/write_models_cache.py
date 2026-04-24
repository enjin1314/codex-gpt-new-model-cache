#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
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
    if not isinstance(tag_name, str) or not tag_name.startswith("rust-v"):
        return None
    version = tag_name.removeprefix("rust-v")
    return version if version else None


def main() -> None:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    cache_path = codex_home / "models_cache.json"
    backup_path = codex_home / "models_cache.json.bak"

    with TEMPLATE_PATH.open("r", encoding="utf-8") as template_file:
        cache = json.load(template_file)

    cache["fetched_at"] = iso_utc_after_30_days()
    cache["client_version"] = (
        existing_cache_version(cache_path)
        or latest_github_release_version()
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
