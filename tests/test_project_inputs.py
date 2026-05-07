from pathlib import Path

import pytest

from project_inputs import pick_notes_txt, resolve_bundled_project


def test_pick_notes_prefers_notes_txt(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("a")
    (tmp_path / "other.txt").write_text("b")
    assert pick_notes_txt(tmp_path).name == "notes.txt"


def test_pick_notes_ambiguous_returns_none(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("1")
    (tmp_path / "b.txt").write_text("2")
    assert pick_notes_txt(tmp_path) is None


def test_pick_notes_single_non_readme(tmp_path: Path) -> None:
    (tmp_path / "visit.txt").write_text("story")
    picked = pick_notes_txt(tmp_path)
    assert picked is not None and picked.name == "visit.txt"


def test_resolve_bundled_project_finds_mov(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("we ate pasta")
    clip = tmp_path / "clip.mov"
    clip.write_bytes(b"")
    root, notes = resolve_bundled_project(tmp_path, recursive=False)
    assert root == tmp_path.resolve()
    assert notes.name == "notes.txt"


def test_resolve_rejects_no_video(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("x")
    with pytest.raises(SystemExit, match=r"No supported videos"):
        resolve_bundled_project(tmp_path, recursive=False)
