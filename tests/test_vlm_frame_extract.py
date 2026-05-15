import pytest

from vlm.frame_extract import sample_shot_timestamps_sec


def test_sample_shot_timestamps_one_per_second():
    assert sample_shot_timestamps_sec(2.2, 5.8) == [3.0, 4.0, 5.0]


def test_sample_shot_timestamps_caps_long_shots():
    times = sample_shot_timestamps_sec(0.0, 20.0, max_frames=8)
    assert len(times) == 8
    assert times[0] == 0.0


def test_sample_shot_timestamps_point_range():
    assert sample_shot_timestamps_sec(4.5, 4.5) == [4.5]


def test_sample_shot_timestamps_clamps_to_clip_duration():
    assert sample_shot_timestamps_sec(0.0, 8.0, clip_duration_sec=2.97) == [0.0, 1.0, 2.0]


def test_sample_shot_timestamps_all_within_clip_bounds():
    duration = 2.97
    times = sample_shot_timestamps_sec(0.0, 8.0, clip_duration_sec=duration)
    assert all(0.0 <= t <= duration - 0.05 for t in times)


def test_sample_shot_timestamps_point_range_clamped_to_clip():
    assert sample_shot_timestamps_sec(3.0, 3.0, clip_duration_sec=2.97) == [pytest.approx(2.92)]
