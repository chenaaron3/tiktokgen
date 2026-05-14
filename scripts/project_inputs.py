"""Repo-root path resolution, run directory layout, bundled footage + ``notes.yaml``."""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAFE_DIR_PART_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def resolve_project_path(path: Path) -> Path:
    expanded = path.expanduser()
    return expanded.resolve() if expanded.is_absolute() else (PROJECT_ROOT / expanded).resolve()


def source_cache_key(source_dir: Path) -> str:
    """
    Build a human-readable stable cache key from source directory path.

    Uses ``PROJECT_ROOT``-relative parts when possible; otherwise uses the source folder name.
    """
    resolved = source_dir.resolve()
    try:
        relative = resolved.relative_to(PROJECT_ROOT)
        parts = relative.parts
    except ValueError:
        parts = (resolved.name,)

    cleaned_parts: list[str] = []
    for part in parts:
        clean = SAFE_DIR_PART_RE.sub("-", part.strip().lower()).strip("._-")
        if clean:
            cleaned_parts.append(clean)

    key = "-".join(cleaned_parts) if cleaned_parts else "source"
    return key[:96].rstrip("-")


def resolve_run_directory(
    *,
    cache_dir_arg: Path,
    source_dir: Path,
) -> Path:
    """Pick source-keyed run directory under ``cache-dir``."""
    cache_base = resolve_project_path(cache_dir_arg)
    cache_base.mkdir(parents=True, exist_ok=True)
    run = (cache_base / source_cache_key(source_dir)).resolve()
    print(f"Using source-keyed run directory: {run}")
    return run
