"""Repo-root path resolution, run directory layout, bundled footage + ``notes.yaml``."""

from __future__ import annotations

import re
from pathlib import Path

from vlm.media import discover_videos

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


def pick_notes_yaml(project_dir: Path) -> Path | None:
    """Return ``project_dir/notes.yaml`` if that file exists; otherwise ``None``."""
    project_dir = project_dir.resolve()
    path = project_dir / "notes.yaml"
    return path.resolve() if path.is_file() else None


def resolve_bundled_project(source: Path) -> tuple[Path, Path]:
    """
    Resolve ``source`` to a bundled project folder: videos for VLM plus ``notes.yaml`` (exact name).

    Relative paths resolve under ``PROJECT_ROOT`` (see ``resolve_project_path``).

    Returns ``(footage_root, notes_path)`` for VLM + script generation.
    """
    resolved_root = resolve_project_path(source)
    if resolved_root.is_file():
        raise SystemExit(
            "SOURCE must be a **project directory** (videos + notes.yaml alongside), not a single file. "
            "Put clips and notes.yaml in one folder and pass that path—for example assets/2026-05-03."
        )
    if not resolved_root.is_dir():
        raise SystemExit(
            f"Bundled mode expects a directory with videos + notes.yaml: not a directory ({resolved_root})."
        )

    notes = pick_notes_yaml(resolved_root)
    if notes is None:
        raise SystemExit(
            f"Bundled mode requires {resolved_root / 'notes.yaml'}. "
            "Create that file (exact name, YAML format) in the project folder beside your clips."
        )

    try:
        discover_videos(resolved_root)
    except FileNotFoundError as error:
        raise SystemExit(str(error)) from None
    except ValueError as error:
        raise SystemExit(str(error)) from None

    return resolved_root, notes
