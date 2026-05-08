from pathlib import Path

import pytest

from util.path_util import pick_notes_txt, resolve_bundled_project


def test_pick_notes_txt_found(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("a")
    (tmp_path / "other.txt").write_text("b")
    assert pick_notes_txt(tmp_path).name == "notes.txt"


def test_pick_notes_txt_missing(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("1")
    assert pick_notes_txt(tmp_path) is None


def test_resolve_bundled_project_finds_mov(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("we ate pasta")
    clip = tmp_path / "clip.mov"
    clip.write_bytes(b"")
    root, notes = resolve_bundled_project(tmp_path)
    assert root == tmp_path.resolve()
    assert notes.name == "notes.txt"


def test_resolve_requires_notes_txt_name(tmp_path: Path) -> None:
    (tmp_path / "story.txt").write_text("x")
    (tmp_path / "clip.mov").write_bytes(b"")
    with pytest.raises(SystemExit, match=r"notes\.txt"):
        resolve_bundled_project(tmp_path)


def test_resolve_rejects_no_video(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("x")
    with pytest.raises(SystemExit, match=r"No supported videos"):
        resolve_bundled_project(tmp_path)
