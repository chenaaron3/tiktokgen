"""TwelveLabs-specific video analysis provider."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from media_metadata import probe_media
from twelvelabs import TwelveLabs
from twelvelabs.types import AsyncResponseFormat, VideoContext_AssetId
from vlm_schema import Clip, Moment, TwelveLabsClipRef


HASH_CHUNK_BYTES = 4 * 1024 * 1024
POLL_INTERVAL_SEC = 5.0

SEGMENT_DEFINITION = {
    "id": "moments",
    "description": (
        "Segment this video into short, simple, useful content moments for reviewing raw footage. "
        "Prefer moments around 2 seconds long and split whenever the subject, action, camera motion, "
        "composition, useful audio, or visible context changes. Avoid broad scene-level segments. "
        "Focus on what is visible, what changes, what is said, what is heard, and whether the moment "
        "is visually usable. Do not make editing, framing, captioning, or orchestration decisions."
    ),
    "fields": [
        {
            "name": "description",
            "type": "string",
            "description": "One concise sentence describing what happens in this moment.",
        },
        {
            "name": "subjects",
            "type": "array",
            "items": {"type": "string"},
            "description": "Visible people, places, foods, objects, landmarks, or other subjects.",
        },
        {
            "name": "actions",
            "type": "array",
            "items": {"type": "string"},
            "description": "Important actions, motion, reveals, gestures, or changes in this moment.",
        },
        {
            "name": "visible_text",
            "type": "array",
            "items": {"type": "string"},
            "description": "Readable on-screen text such as signs, menus, labels, or captions.",
        },
        {
            "name": "spoken_transcript",
            "type": "string",
            "description": (
                "Verbatim or near-verbatim spoken words heard in this moment. "
                "Return an empty string if there is no clear speech."
            ),
        },
        {
            "name": "audio",
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Relevant non-speech audio cues such as sizzling, crowd noise, music, traffic, "
                "water, applause, or silence."
            ),
        },
        {
            "name": "quality",
            "type": "string",
            "description": (
                "Simple visual usability rating for this moment. Consider clarity, sharpness, "
                "exposure, stability, and whether the subject is easy to understand."
            ),
            "enum": ["great", "good", "okay", "poor"],
        },
        {
            "name": "issues",
            "type": "array",
            "items": {"type": "string"},
            "description": "Simple quality or clarity issues such as shaky, blurry, dark, obstructed, or unclear.",
        },
        {
            "name": "why_useful",
            "type": "string",
            "description": (
                "One short editor-style note explaining why this moment may be useful as raw material. "
                "Keep this descriptive, not prescriptive."
            ),
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


def require_api_key() -> str:
    api_key = os.environ.get("TWELVELABS_API_KEY")
    if not api_key:
        raise RuntimeError("Set TWELVELABS_API_KEY before running TwelveLabs analysis.")
    return api_key


def as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def normalize_quality(value: Any) -> str:
    quality = str(value or "okay").lower()
    if quality in {"great", "good", "okay", "poor"}:
        return quality
    return "okay"


def normalize_moments(raw_data: dict[str, Any]) -> list[Moment]:
    raw_moments = raw_data.get("moments", [])
    normalized = []

    for index, moment in enumerate(raw_moments, start=1):
        metadata = moment.get("metadata", {})
        normalized.append(
            Moment(
                momentId=f"moment-{index:03d}",
                startSec=float(moment.get("start_time", 0)),
                endSec=float(moment.get("end_time", moment.get("start_time", 0))),
                description=metadata.get("description", ""),
                subjects=as_string_list(metadata.get("subjects")),
                actions=as_string_list(metadata.get("actions")),
                visibleText=as_string_list(metadata.get("visible_text")),
                spokenText=metadata.get("spoken_transcript", ""),
                audio=as_string_list(metadata.get("audio")),
                quality=normalize_quality(metadata.get("quality")),
                issues=as_string_list(metadata.get("issues")),
                whyUseful=metadata.get("why_useful", ""),
            )
        )

    return normalized


class TwelveLabsVideoAnalyzer:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "pegasus1.5",
        min_segment_duration: float = 2.0,
        max_segment_duration: float = 3.0,
    ) -> None:
        self.client = TwelveLabs(api_key=api_key or require_api_key())
        self.model = model
        self.min_segment_duration = min_segment_duration
        self.max_segment_duration = max_segment_duration

    def analyze_video(self, video_path: Path) -> tuple[Clip, dict[str, Any]]:
        media = probe_media(video_path)
        asset = self._get_or_create_asset(video_path)
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
        print(f"[{video_path.name}] Created TwelveLabs analysis task: {task.task_id}")

        print(f"[{video_path.name}] Waiting for analysis task")
        task = self._wait_for_task(task.task_id)
        raw_data = json.loads(task.result.data)
        resolved_clip_id = video_path.stem
        moments = normalize_moments(raw_data)
        summary = " ".join(moment.description for moment in moments[:3]).strip()
        clip = Clip(
            id=resolved_clip_id,
            sourcePath=str(video_path),
            originalFilename=video_path.name,
            durationSec=media.get("durationSec"),
            capturedAt=media.get("captureMetadata", {}).get("capturedAt"),
            location=media.get("captureMetadata", {}).get("location"),
            media=media,
            twelveLabs=TwelveLabsClipRef(assetId=asset.id, taskId=task.task_id),
            summary=summary,
            moments=moments,
        )
        raw_clip = {
            "clipId": resolved_clip_id,
            "sourcePath": str(video_path),
            "assetId": asset.id,
            "taskId": task.task_id,
            "data": raw_data,
        }
        return clip, raw_clip

    def _get_or_create_asset(self, video_path: Path) -> Any:
        filename = deterministic_asset_filename(video_path)
        existing_asset = self._find_asset(filename)
        if existing_asset is not None:
            status = getattr(existing_asset, "status", None)
            if status == "ready":
                print(f"[{video_path.name}] Reusing TwelveLabs asset: {existing_asset.id}")
                return existing_asset
            if status != "failed":
                print(f"[{video_path.name}] Waiting for existing TwelveLabs asset: {existing_asset.id}")
                return self._wait_for_asset(existing_asset.id)

        print(f"[{video_path.name}] Uploading video as {filename}")
        with video_path.open("rb") as video_file:
            asset = self.client.assets.create(method="direct", file=video_file, filename=filename)
        print(f"[{video_path.name}] Created TwelveLabs asset: {asset.id}")

        print(f"[{video_path.name}] Waiting for asset processing")
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
