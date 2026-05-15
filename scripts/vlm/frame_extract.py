"""Extract still frames from source clips for GPT shot verification."""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

MAX_VERIFY_FRAMES_PER_SHOT = 3
# Stay slightly inside EOF so ffmpeg always has a decodable frame.
_CLIP_END_MARGIN_SEC = 0.05


def _bound_timestamps_to_clip(
    timestamps: list[float],
    clip_duration_sec: float | None,
) -> list[float]:
    if clip_duration_sec is None or clip_duration_sec <= 0:
        return timestamps
    max_sec = max(0.0, clip_duration_sec - _CLIP_END_MARGIN_SEC)
    return [min(max(0.0, t), max_sec) for t in timestamps]


def sample_shot_timestamps_sec(
    start_sec: float,
    end_sec: float,
    *,
    max_frames: int = MAX_VERIFY_FRAMES_PER_SHOT,
    clip_duration_sec: float | None = None,
) -> list[float]:
    """One sample per integer second inside ``[start_sec, end_sec]`` (clip timeline)."""
    if clip_duration_sec is not None and clip_duration_sec > 0:
        end_sec = min(end_sec, max(start_sec, clip_duration_sec - 1e-3))
    if end_sec < start_sec:
        raise ValueError("end_sec must be >= start_sec")
    if math.isclose(start_sec, end_sec, abs_tol=1e-6):
        return _bound_timestamps_to_clip([start_sec], clip_duration_sec)

    first = int(math.ceil(start_sec))
    last = int(math.floor(end_sec))
    if first > last:
        return _bound_timestamps_to_clip([start_sec], clip_duration_sec)

    times = [float(second) for second in range(first, last + 1)]
    if len(times) <= max_frames:
        return _bound_timestamps_to_clip(times, clip_duration_sec)

    stride = len(times) / max_frames
    picked: list[float] = []
    for index in range(max_frames):
        pick = times[min(int(index * stride), len(times) - 1)]
        if pick not in picked:
            picked.append(pick)
    return _bound_timestamps_to_clip(picked, clip_duration_sec)


def extract_frame_jpeg(
    video_path: Path,
    timestamp_sec: float,
    output_path: Path,
) -> Path:
    """Extract a single frame at ``timestamp_sec`` using ffmpeg."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    seek_sec = max(0.0, timestamp_sec)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{seek_sec:.3f}",
        "-i",
        str(video_path),
        # iPhone MOV often yields limited-range YUV; MJPEG needs full-range (yuvj420p).
        "-vf",
        "format=yuvj420p",
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output_path),
    ]
    try:
        subprocess.run(command, capture_output=True, text=True, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg not found on PATH (required for shot verification)") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(
            f"ffmpeg failed to extract frame at {seek_sec:.3f}s from {video_path.name}: {detail}"
        ) from exc
    if not output_path.is_file():
        raise RuntimeError(f"ffmpeg did not write frame: {output_path}")
    return output_path
