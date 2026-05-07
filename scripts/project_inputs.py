"""Resolve a single “project” folder that contains videos + a notes .txt file."""

from __future__ import annotations

from pathlib import Path

from vlm.media import discover_videos

# Filenames to ignore when scanning for a lone story / notes file (not exhaustive).
_SKIPPED_TXT_NAMES = frozenset(
    name.lower()
    for name in (
        "readme.txt",
        "read_me.txt",
        "license.txt",
        "changelog.txt",
        "credits.txt",
    )
)


def pick_notes_txt(project_dir: Path) -> Path | None:
    """
    Prefer ``notes.txt``. Otherwise, if exactly one non-ignored ``*.txt`` exists, use it.
    If several story-like files remain, return ``None`` (caller surfaces an error).
    """
    project_dir = project_dir.resolve()
    preferred = project_dir / "notes.txt"
    if preferred.is_file():
        return preferred.resolve()

    candidates: list[Path] = []
    for path in sorted(project_dir.glob("*.txt")):
        if not path.is_file():
            continue
        if path.name.lower() in _SKIPPED_TXT_NAMES:
            continue
        candidates.append(path)

    if len(candidates) == 1:
        return candidates[0].resolve()
    return None


def resolve_bundled_project(project_dir: Path, *, recursive: bool) -> tuple[Path, Path]:
    """
    ``project_dir`` contains video files and exactly one logical notes file.

    Returns ``(footage_root, notes_path)`` for VLM + script generation.
    """
    project_dir = project_dir.expanduser()
    if not project_dir.is_dir():
        raise SystemExit(
            f"Bundled mode expects a directory with videos + notes: not a directory ({project_dir}). "
            "Use --notes-file if you are passing a single video file."
        )

    resolved_dir = project_dir.resolve()
    notes = pick_notes_txt(resolved_dir)
    if notes is None:
        ambiguous = sorted(p for p in resolved_dir.glob("*.txt") if p.is_file())
        names = [p.name for p in ambiguous]
        story_like = [n for n in names if n.lower() not in _SKIPPED_TXT_NAMES]
        ignored = [n for n in names if n.lower() in _SKIPPED_TXT_NAMES]
        if len(story_like) > 1:
            raise SystemExit(
                f"Multiple story .txt files in {resolved_dir}: {', '.join(story_like)}. "
                "Rename the one you want to notes.txt, or pass --notes-file PATH explicitly."
            )
        raise SystemExit(
            f"No notes file in {resolved_dir}. "
            "Add notes.txt (recommended) or exactly one other .txt (besides readme/license), "
            "or pass --notes-file."
            + (f" (Ignored .txt: {', '.join(ignored)})" if ignored else "")
        )

    try:
        discover_videos(resolved_dir, recursive=recursive)
    except FileNotFoundError as error:
        raise SystemExit(str(error)) from None
    except ValueError as error:
        raise SystemExit(str(error)) from None

    return resolved_dir, notes
