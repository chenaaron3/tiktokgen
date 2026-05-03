"""Helpers for discovering videos and extracting local media metadata."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any


VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".webm"}


def discover_videos(source: Path, *, recursive: bool) -> list[Path]:
    """Return supported videos for a file or directory source."""
    if source.is_file():
        if source.suffix.lower() not in VIDEO_EXTENSIONS:
            raise ValueError(f"Unsupported video extension: {source.suffix}")
        return [source]

    if not source.is_dir():
        raise FileNotFoundError(f"Source does not exist: {source}")

    pattern = "**/*" if recursive else "*"
    videos = sorted(
        path
        for path in source.glob(pattern)
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )
    if not videos:
        raise FileNotFoundError(f"No supported videos found in: {source}")
    return videos


def parse_iso6709_location(value: str | None) -> dict[str, Any] | None:
    """Parse ISO 6709 location strings used by Apple QuickTime metadata."""
    if not value:
        return None

    match = re.match(r"^([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)?/?$", value.strip())
    if not match:
        return {"raw": value, "source": "metadata"}

    latitude, longitude, altitude = match.groups()
    location: dict[str, Any] = {
        "latitude": float(latitude),
        "longitude": float(longitude),
        "raw": value,
        "source": "metadata",
    }
    if altitude is not None:
        location["altitude"] = float(altitude)
    return location


def collect_tags(ffprobe_data: dict[str, Any]) -> dict[str, Any]:
    """Collect format and stream tags from ffprobe output."""
    tags: dict[str, Any] = {}
    format_tags = ffprobe_data.get("format", {}).get("tags", {})
    if isinstance(format_tags, dict):
        tags.update(format_tags)

    for stream in ffprobe_data.get("streams", []):
        stream_tags = stream.get("tags", {})
        if isinstance(stream_tags, dict):
            for key, value in stream_tags.items():
                tags.setdefault(key, value)

    return tags


def parse_capture_metadata(ffprobe_data: dict[str, Any]) -> dict[str, Any]:
    """Extract captured time and location from ffprobe tags when available."""
    tags = collect_tags(ffprobe_data)
    captured_at = (
        tags.get("com.apple.quicktime.creationdate")
        or tags.get("creation_time")
        or tags.get("date")
    )
    location_raw = (
        tags.get("com.apple.quicktime.location.ISO6709")
        or tags.get("location")
        or tags.get("location-eng")
    )

    return {
        "capturedAt": captured_at,
        "location": parse_iso6709_location(location_raw),
    }


def empty_media_metadata() -> dict[str, Any]:
    return {
        "durationSec": None,
        "width": None,
        "height": None,
        "fps": None,
        "hasAudio": None,
        "orientation": "unknown",
        "captureMetadata": {
            "capturedAt": None,
            "location": None,
        },
    }


def probe_media(video_path: Path) -> dict[str, Any]:
    """Best-effort media probe. Requires ffprobe; falls back to unknown values."""
    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, check=True, text=True)
        data = json.loads(result.stdout)
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError):
        return empty_media_metadata()

    video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
    width = video_stream.get("width")
    height = video_stream.get("height")
    duration = video_stream.get("duration") or data.get("format", {}).get("duration")

    fps = None
    rate = video_stream.get("avg_frame_rate")
    if rate and rate != "0/0":
        numerator, denominator = rate.split("/")
        if float(denominator) != 0:
            fps = float(numerator) / float(denominator)

    orientation = "unknown"
    if width and height:
        if height > width:
            orientation = "vertical"
        elif width > height:
            orientation = "horizontal"
        else:
            orientation = "square"

    return {
        "durationSec": float(duration) if duration else None,
        "width": width,
        "height": height,
        "fps": fps,
        "hasAudio": has_audio,
        "orientation": orientation,
        "captureMetadata": parse_capture_metadata(data),
    }
