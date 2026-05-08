"""TwelveLabs-specific video analysis provider."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from twelvelabs import TwelveLabs
from twelvelabs.types import AsyncResponseFormat, VideoContext_AssetId

from .media import probe_media
from .restaurant_tags import RESTAURANT_SEGMENT_DESCRIPTION, RESTAURANT_VLM_TAGS
from .schema import Clip, IdentifiedShot, TwelveLabsClipRef

# Defaults for TwelveLabs time-based segmentation (used programmatically + CLI fallback).
DEFAULT_ANALYSIS_MODEL_NAME = "pegasus1.5"
MIN_SEGMENT_DURATION_SEC = 2.0
MAX_SEGMENT_DURATION_SEC = 4.0

HASH_CHUNK_BYTES = 4 * 1024 * 1024
POLL_INTERVAL_SEC = 5.0

SEGMENT_DEFINITION = {
    "id": "identified_shots",
    "description": RESTAURANT_SEGMENT_DESCRIPTION,
    "fields": [
        {
            "name": "vlm_tag",
            "type": "string",
            "description": "One enum slug that best matches the segment visuals.",
            "enum": list(RESTAURANT_VLM_TAGS),
        },
        {
            "name": "key_instant_sec",
            "type": "number",
            "description": (
                "Seconds on master timeline with start_time<=value<=end_time. "
                "Decisive instant for the tag; for not_suitable use clearest or midpoint frame in the span."
            ),
        },
        {
            "name": "confidence_score",
            "type": "number",
            "description": "0.0-1.0 confidence for the tag.",
        },
        {
            "name": "reasoning",
            "type": "string",
            "description": "One short sentence with visual evidence for the tag.",
        },
    ],
}


def video_asset_key(video_path: Path, *, chunk_bytes: int = HASH_CHUNK_BYTES) -> str:
    """Hash file size plus first and last chunks for a fast stable asset key."""
    size = video_path.stat().st_size
    digest = hashlib.sha256()
    digest.update(str(size).encode("utf-8"))
    digest.update(b"\0")

    with video_path.open("rb") as file:
        digest.update(file.read(chunk_bytes))
        if size > chunk_bytes:
            file.seek(max(0, size - chunk_bytes))
            digest.update(file.read(chunk_bytes))

    return digest.hexdigest()[:24]


def deterministic_asset_filename(video_path: Path) -> str:
    return f"{video_path.stem}__sha256_{video_asset_key(video_path)}{video_path.suffix}"


def twelvelabs_upload_filename(logical_source: Path, file_to_upload: Path) -> str:
    """Stable asset name for TwelveLabs; distinguishes padded MP4 derivatives from the source file."""
    base = deterministic_asset_filename(logical_source)
    if file_to_upload.resolve() == logical_source.resolve():
        return base
    return f"{Path(base).stem}__tw_minpad.mp4"


def require_api_key() -> str:
    api_key = os.environ.get("TWELVELABS_API_KEY")
    if not api_key:
        raise RuntimeError("Set TWELVELABS_API_KEY before running TwelveLabs analysis.")
    return api_key


def normalize_confidence(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, score))


def parse_required_key_instant(
    metadata: dict[str, Any],
    *,
    start_sec: float,
    end_sec: float,
    row_index: int,
) -> float:
    """Metadata key_instant_sec is required and must fall within [start_sec, end_sec]."""
    raw = metadata.get("key_instant_sec")
    if raw is None:
        raise RuntimeError(
            f"identified_shots[{row_index}]: missing required metadata field key_instant_sec"
        )
    try:
        key = float(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"identified_shots[{row_index}]: key_instant_sec is not a number: {raw!r}"
        ) from exc

    low, high = (start_sec, end_sec) if end_sec >= start_sec else (end_sec, start_sec)

    if key < low or key > high:
        raise RuntimeError(
            f"identified_shots[{row_index}]: key_instant_sec {key} must lie within [{low}, {high}]"
        )
    return key


def normalize_identified_shots(raw_data: dict[str, Any]) -> list[IdentifiedShot]:
    raw_shots = raw_data.get("identified_shots")
    if not raw_shots and "moments" in raw_data:
        raw_shots = raw_data.get("moments")
    if not isinstance(raw_shots, list):
        raw_shots = []

    normalized: list[IdentifiedShot] = []
    for index, row in enumerate(raw_shots, start=1):
        if not isinstance(row, dict):
            continue
        metadata = row.get("metadata") or {}
        tag = str(metadata.get("vlm_tag", "")).strip()
        start_raw = float(row.get("start_time", 0))
        end_raw = float(row.get("end_time", row.get("start_time", 0)))
        start_sec, end_sec = (
            (start_raw, end_raw) if end_raw >= start_raw else (end_raw, start_raw)
        )
        key_instant = parse_required_key_instant(
            metadata, start_sec=start_sec, end_sec=end_sec, row_index=index
        )
        normalized.append(
            IdentifiedShot(
                momentId=f"shot-{index:03d}",
                startSec=start_sec,
                endSec=end_sec,
                vlmTag=tag,
                confidenceScore=normalize_confidence(metadata.get("confidence_score")),
                keyInstantSec=key_instant,
                reasoning=str(metadata.get("reasoning", "")).strip(),
            )
        )

    normalized.sort(key=lambda s: s.start_sec)
    return normalized

def build_clip_summary(shots: list[IdentifiedShot], *, max_items: int = 4) -> str:
    parts: list[str] = []
    for shot in shots[:max_items]:
        reason = shot.reasoning.strip()
        if len(reason) > 120:
            reason = reason[:117] + "..."
        if reason:
            parts.append(f"{shot.vlm_tag}: {reason}")
        else:
            parts.append(shot.vlm_tag)
    return " | ".join(parts).strip()


class TwelveLabsVideoAnalyzer:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        min_segment_duration: float | None = None,
        max_segment_duration: float | None = None,
    ) -> None:
        self.client = TwelveLabs(api_key=api_key or require_api_key())
        self.model = model if model is not None else DEFAULT_ANALYSIS_MODEL_NAME
        self.min_segment_duration = (
            min_segment_duration if min_segment_duration is not None else MIN_SEGMENT_DURATION_SEC
        )
        self.max_segment_duration = (
            max_segment_duration if max_segment_duration is not None else MAX_SEGMENT_DURATION_SEC
        )

    def analyze_video(
        self,
        video_path: Path,
        *,
        clip_source_path: Path | None = None,
        clip_media: dict[str, Any] | None = None,
    ) -> tuple[Clip, dict[str, Any]]:
        logical_source = clip_source_path if clip_source_path is not None else video_path
        media = clip_media if clip_media is not None else probe_media(logical_source)
        upload_name = twelvelabs_upload_filename(logical_source, video_path)
        asset = self._get_or_create_asset(
            video_path,
            upload_filename=upload_name,
            log_clip_name=logical_source.name,
        )
        task = self.client.analyze_async.tasks.create(
            video=VideoContext_AssetId(asset_id=asset.id),
            model_name=self.model,
            analysis_mode="time_based_metadata",
            min_segment_duration=self.min_segment_duration,
            max_segment_duration=self.max_segment_duration,
            response_format=AsyncResponseFormat(
                type="segment_definitions",
                segment_definitions=[SEGMENT_DEFINITION],
            ),
        )
        print(f"[{logical_source.name}] Created TwelveLabs analysis task: {task.task_id}")

        print(f"[{logical_source.name}] Waiting for analysis task")
        task = self._wait_for_task(task.task_id)
        raw_data = json.loads(task.result.data)
        resolved_clip_id = logical_source.stem
        identified_shots = normalize_identified_shots(raw_data)
        summary = build_clip_summary(identified_shots)
        clip = Clip(
            id=resolved_clip_id,
            sourcePath=str(logical_source),
            originalFilename=logical_source.name,
            durationSec=media.get("durationSec"),
            capturedAt=media.get("captureMetadata", {}).get("capturedAt"),
            location=media.get("captureMetadata", {}).get("location"),
            media=media,
            twelveLabs=TwelveLabsClipRef(assetId=asset.id, taskId=task.task_id),
            summary=summary,
            identifiedShots=identified_shots,
        )
        raw_clip = {
            "clipId": resolved_clip_id,
            "sourcePath": str(logical_source),
            "assetId": asset.id,
            "taskId": task.task_id,
            "data": raw_data,
        }
        return clip, raw_clip

    def _get_or_create_asset(
        self,
        video_path: Path,
        *,
        upload_filename: str | None = None,
        log_clip_name: str | None = None,
    ) -> Any:
        filename = upload_filename or deterministic_asset_filename(video_path)
        label = log_clip_name or video_path.name
        existing_asset = self._find_asset(filename)
        if existing_asset is not None:
            status = getattr(existing_asset, "status", None)
            if status == "ready":
                print(f"[{label}] Reusing TwelveLabs asset: {existing_asset.id}")
                return existing_asset
            if status != "failed":
                print(f"[{label}] Waiting for existing TwelveLabs asset: {existing_asset.id}")
                return self._wait_for_asset(existing_asset.id)

        print(f"[{label}] Uploading video as {filename}")
        with video_path.open("rb") as video_file:
            asset = self.client.assets.create(method="direct", file=video_file, filename=filename)
        print(f"[{label}] Created TwelveLabs asset: {asset.id}")

        print(f"[{label}] Waiting for asset processing")
        return self._wait_for_asset(asset.id)

    def _find_asset(self, filename: str) -> Any | None:
        pager = self.client.assets.list(filename=filename, asset_types="video", page_limit=50)
        for asset in pager:
            asset_filename = getattr(asset, "filename", None) or getattr(asset, "file_name", None)
            if asset_filename != filename:
                continue
            return asset
        return None

    def _wait_for_asset(self, asset_id: str) -> Any:
        while True:
            asset = self.client.assets.retrieve(asset_id)
            if asset.status == "ready":
                return asset
            if asset.status == "failed":
                raise RuntimeError(f"TwelveLabs asset processing failed: {asset_id}")
            print(f"Asset status: {asset.status}")
            time.sleep(POLL_INTERVAL_SEC)

    def _wait_for_task(self, task_id: str) -> Any:
        while True:
            task = self.client.analyze_async.tasks.retrieve(task_id)
            if task.status == "ready":
                return task
            if task.status == "failed":
                raise RuntimeError(f"TwelveLabs analysis task failed: {task_id}")
            print(f"Task status: {task.status}")
            time.sleep(POLL_INTERVAL_SEC)
