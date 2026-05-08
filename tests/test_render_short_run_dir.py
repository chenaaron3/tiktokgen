import os
import time

from pathlib import Path

import pytest

from project_inputs import find_latest_run_directory, resolve_run_directory


def test_find_latest_run_directory_picks_recent(tmp_path: Path) -> None:
    old = tmp_path / "old-run"
    new = tmp_path / "new-run"
    old.mkdir()
    new.mkdir()
    now = time.time()
    os.utime(old, (now - 100, now - 100))
    os.utime(new, (now, now))
    assert find_latest_run_directory(tmp_path) == new


def test_find_latest_empty_returns_none(tmp_path: Path) -> None:
    assert find_latest_run_directory(tmp_path) is None


def test_resolve_run_dir_explicit_roundtrip(tmp_path: Path, monkeypatch) -> None:
    explicit = tmp_path / "my-run"
    monkeypatch.chdir(tmp_path.parent)
    out = resolve_run_directory(
        run_dir_arg=explicit,
        resume=False,
        cache_dir_arg=tmp_path / "unused-cache",
    )
    assert out == explicit.resolve()


def test_resolve_resume_conflict(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="not both"):
        resolve_run_directory(
            run_dir_arg=tmp_path / "explicit-run-id",
            resume=True,
            cache_dir_arg=tmp_path / "cache",
        )


def test_resolve_new_uuid_under_cache(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    out = resolve_run_directory(run_dir_arg=None, resume=False, cache_dir_arg=cache)
    assert out.parent.resolve() == cache.resolve()
    assert len(out.name) > 24


def test_resume_requires_existing_subdirectory(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    with pytest.raises(SystemExit, match=r"No run directories"):
        resolve_run_directory(run_dir_arg=None, resume=True, cache_dir_arg=cache)
