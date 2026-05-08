"""Repo-root path resolution, run directory layout, bundled footage + ``notes.txt``."""

from __future__ import annotations

from pathlib import Path

from uuid6 import uuid7

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resolve_project_path(path: Path) -> Path:
    expanded = path.expanduser()
    return expanded.resolve() if expanded.is_absolute() else (PROJECT_ROOT / expanded).resolve()


def find_latest_run_directory(cache_dir: Path) -> Path | None:
    """Return the subdirectory of `cache_dir` with the newest ``st_mtime``, or ``None`` if empty."""
    if not cache_dir.is_dir():
        return None
    candidates = [
        p for p in cache_dir.iterdir() if p.is_dir() and not p.name.startswith(".")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def resolve_run_directory(
    *,
    run_dir_arg: Path | None,
    resume: bool,
    cache_dir_arg: Path,
) -> Path:
    """Pick explicit ``--run-dir``, latest under cache (``--resume``), or ``cache-dir/<new-uuid>``."""
    if run_dir_arg is not None and resume:
        raise SystemExit("Use only one of --run-dir or --resume (not both).")
    cache_base = resolve_project_path(cache_dir_arg)
    cache_base.mkdir(parents=True, exist_ok=True)
    if run_dir_arg is not None:
        return resolve_project_path(run_dir_arg)
    if resume:
        latest = find_latest_run_directory(cache_base)
        if latest is None:
            raise SystemExit(
                f"No run directories found under {cache_base}; "
                "run without --resume to create a new UUID run folder."
            )
        print(f"Resuming latest run: {latest}")
        return latest
    new_id = str(uuid7())
    run = cache_base / new_id
    print(f"New run directory: {run}")
    return run
