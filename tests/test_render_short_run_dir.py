from datetime import datetime, timezone
from pathlib import Path

import pytest

from project_inputs import create_run_directory, find_latest_run_directory, resolve_run_directory


def test_find_latest_run_directory_picks_latest_timestamp_name(tmp_path: Path) -> None:
    old = tmp_path / "20260508-195959"
    new = tmp_path / "20260508-200000"
    old.mkdir()
    new.mkdir()
    assert find_latest_run_directory(tmp_path) == new


def test_find_latest_run_directory_ignores_non_timestamp_names(tmp_path: Path) -> None:
    (tmp_path / "019e0648-d859-79d1-bd1c-dcf5e431e360").mkdir()
    (tmp_path / "random-dir").mkdir()
    (tmp_path / "20260508-200000").mkdir()
    assert find_latest_run_directory(tmp_path) == (tmp_path / "20260508-200000")


def test_find_latest_empty_returns_none(tmp_path: Path) -> None:
    assert find_latest_run_directory(tmp_path) is None


def test_resolve_run_id_under_cache(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    run_name = "20260508-203145"
    expected = cache / run_name
    expected.mkdir(parents=True, exist_ok=True)
    out = resolve_run_directory(
        run_id=run_name,
        resume=False,
        cache_dir_arg=cache,
    )
    assert out == expected.resolve()


def test_resolve_run_id_rejects_path(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    with pytest.raises(SystemExit, match="single folder name"):
        resolve_run_directory(
            run_id="evil/../nested",
            resume=False,
            cache_dir_arg=cache,
        )


def test_resolve_run_id_rejects_non_timestamp_format(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    with pytest.raises(SystemExit, match=r"must match YYYYMMDD-HHMMSS"):
        resolve_run_directory(
            run_id="some-id",
            resume=False,
            cache_dir_arg=cache,
        )


def test_resolve_resume_conflict(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="not both"):
        resolve_run_directory(
            run_id="20260508-203145",
            resume=True,
            cache_dir_arg=tmp_path / "cache",
        )


def test_resolve_new_timestamp_under_cache(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    out = resolve_run_directory(run_id=None, resume=False, cache_dir_arg=cache)
    assert out.parent.resolve() == cache.resolve()
    assert out.name.count("-") in {1, 2}
    assert len(out.name) in {15, 18}


def test_create_run_directory_adds_counter_suffix_on_collision(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "20260508-203145").mkdir()
    (cache / "20260508-203145-01").mkdir()
    fixed_now = datetime(2026, 5, 8, 20, 31, 45, tzinfo=timezone.utc)
    out = create_run_directory(cache, now=fixed_now)
    assert out.name == "20260508-203145-02"


def test_resume_requires_existing_subdirectory(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    with pytest.raises(SystemExit, match=r"No run directories"):
        resolve_run_directory(run_id=None, resume=True, cache_dir_arg=cache)


def test_resume_ignores_non_timestamp_subdirectories(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "019e0648-d859-79d1-bd1c-dcf5e431e360").mkdir()
    with pytest.raises(SystemExit, match=r"No run directories"):
        resolve_run_directory(run_id=None, resume=True, cache_dir_arg=cache)
