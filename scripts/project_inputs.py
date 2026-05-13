"""Repo-root path resolution, run directory layout, bundled footage + ``notes.yaml``."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_ID_RE = re.compile(r"^\d{8}-\d{6}(?:-\d{2})?$")


def resolve_project_path(path: Path) -> Path:
    expanded = path.expanduser()
    return expanded.resolve() if expanded.is_absolute() else (PROJECT_ROOT / expanded).resolve()


def find_latest_run_directory(cache_dir: Path) -> Path | None:
    """Return the lexicographically latest timestamp run subdirectory, or ``None`` if empty."""
    if not cache_dir.is_dir():
        return None
    candidates = [
        p
        for p in cache_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".") and RUN_ID_RE.fullmatch(p.name)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.name)


def create_run_id(now: datetime | None = None) -> str:
    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    return timestamp


def create_run_directory(cache_base: Path, now: datetime | None = None) -> Path:
    """Create a unique timestamp run directory under ``cache_base``."""
    base_id = create_run_id(now)
    candidate = cache_base / base_id
    if not candidate.exists():
        return candidate

    index = 1
    while True:
        candidate = cache_base / f"{base_id}-{index:02d}"
        if not candidate.exists():
            return candidate
        index += 1


def resolve_run_directory(
    *,
    run_id: str | None,
    resume: bool,
    cache_dir_arg: Path,
) -> Path:
    """Pick ``cache-dir/<run-id>``, latest under cache (``--resume``), or ``cache-dir/<new-timestamp>``."""
    if run_id is not None and resume:
        raise SystemExit("Use only one of --run-id or --resume (not both).")
    cache_base = resolve_project_path(cache_dir_arg)
    cache_base.mkdir(parents=True, exist_ok=True)
    if run_id is not None:
        rid = run_id.strip()
        if not rid:
            raise SystemExit("--run-id must not be empty.")
        if rid in {".", ".."} or "/" in rid or "\\" in rid:
            raise SystemExit("--run-id must be a single folder name, not a path.")
        if RUN_ID_RE.fullmatch(rid) is None:
            raise SystemExit("--run-id must match YYYYMMDD-HHMMSS or YYYYMMDD-HHMMSS-##.")
        return (cache_base / rid).resolve()
    if resume:
        latest = find_latest_run_directory(cache_base)
        if latest is None:
            raise SystemExit(
                f"No run directories found under {cache_base}; "
                "run without --resume to create a new timestamp run folder."
            )
        print(f"Resuming latest run: {latest}")
        return latest
    run = create_run_directory(cache_base)
    print(f"New run directory: {run}")
    return run
