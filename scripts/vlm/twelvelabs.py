"""TwelveLabs-specific video analysis provider."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, cast

from twelvelabs import TwelveLabs
from twelvelabs.types import AsyncResponseFormat, VideoContext_AssetId

from .media import probe_media
from .notes import ParsedReviewNotes
from .restaurant_tags import RESTAURANT_SEGMENT_DESCRIPTION, RESTAURANT_VLM_TAGS
from .shot_labels import sanitize_dish_name
from .schema import (
    LABEL_CONFIDENCE_VALUES,
    Clip,
    ClipMedia,
    IdentifiedShot,
    LabelConfidence,
    TwelveLabsClipRef,
)

# Defaults for TwelveLabs time-based segmentation (used programmatically + CLI fallback).
DEFAULT_ANALYSIS_MODEL_NAME = "pegasus1.5"
MIN_SEGMENT_DURATION_SEC = 2.0
MAX_SEGMENT_DURATION_SEC = 4.0

HASH_CHUNK_BYTES = 4 * 1024 * 1024
POLL_INTERVAL_SEC = 5.0
SEGMENT_DEFINITION: dict[str, Any] = {
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
            "name": "key_instant_start_sec",
            "type": "number",
            "description": (
                "Seconds on master timeline with start_time<=value<=end_time. "
                "Key moment within the shot with the best framing and timing for the tag."
            ),
        },
        {
            "name": "reasoning",
            "type": "string",
            "description": "One short sentence with visual evidence for the tag.",
        },
        {
            "name": "label_confidence",
            "type": "string",
            "description": (
                "Certainty in the tag and dish_name together: high (clear visuals), "
                "medium (some ambiguity), low (guess or poor quality)."
            ),
            "enum": list(LABEL_CONFIDENCE_VALUES),
        },
        {
            "name": "dish_name",
            "type": "string",
            "description": (
                "Optional dish name only when highly confident and only for food shots tagged "
                "the_preparation, the_interaction, or the_reaction. Use empty string when unknown."
            ),
        },
        {
            "name": "semantic_context",
            "type": "string",
            "description": (
                "Detailed natural-language scene description for shot replacement, including subject, "
                "setting, action, camera/framing, and visible text when present. Use empty string "
                "when unknown."
            ),
        },
    ],
}


def segment_definitions_with_extra_context(additional_context: ParsedReviewNotes | None) -> list[Any]:
    """
    Embed parsed dish context in the segment definition description.
    """
    merged = cast(dict[str, Any], copy.deepcopy(SEGMENT_DEFINITION))
    dish_summaries: list[str] = []
    dish_names: list[str] = []
    seen_names: set[str] = set()
    if additional_context is not None:
        for dish in additional_context.dishes:
            name = dish.name
            description = dish.description
            if name.casefold() not in seen_names:
                seen_names.add(name.casefold())
                dish_names.append(name)
            dish_summaries.append(f"- {name}: {description}")

    if dish_summaries:
        merged["description"] = (
            "Dish context from reviewer notes (name + description only).\n\n"
            + "\n".join(dish_summaries)
            + "\n\n---\n\n"
            + str(merged.get("description", "")).strip()
        )
    if dish_names:
        for field in merged.get("fields", []):
            if not isinstance(field, dict) or field.get("name") != "dish_name":
                continue
            field["enum"] = ["", *dish_names]
            break
    return [merged]


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


def parse_required_key_instant_sec(
    metadata: dict[str, Any],
    *,
    start_sec: float,
    end_sec: float,
    row_index: int,
) -> float:
    """Parse required key instant and clamp into [start_sec, end_sec]."""
    raw_start = metadata.get("key_instant_start_sec")
    if raw_start is None:
        raise RuntimeError(
            f"identified_shots[{row_index}]: missing required metadata field key_instant_start_sec"
        )

    try:
        key_start = float(raw_start)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"identified_shots[{row_index}]: key_instant_start_sec is not a number: {raw_start!r}"
        ) from exc

    low, high = (start_sec, end_sec) if end_sec >= start_sec else (end_sec, start_sec)

    # Be lenient with provider boundary jitter: clamp to segment bounds.
    key_start = min(max(key_start, low), high)
    return key_start


def parse_label_confidence(metadata: dict[str, Any], *, row_index: int) -> LabelConfidence:
    raw = metadata.get("label_confidence")
    if raw is None:
        raise ValueError(f"segment {row_index}: label_confidence is required")
    value = str(raw).strip().lower()
    if value not in LABEL_CONFIDENCE_VALUES:
        raise ValueError(
            f"segment {row_index}: label_confidence must be one of {LABEL_CONFIDENCE_VALUES}, "
            f"got {raw!r}"
        )
    return value  # type: ignore[return-value]


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
        key_instant_start = parse_required_key_instant_sec(
            metadata, start_sec=start_sec, end_sec=end_sec, row_index=index
        )
        dish_name_raw = metadata.get("dish_name")
        dish_name = str(dish_name_raw).strip() if dish_name_raw is not None else ""
        semantic_context_raw = metadata.get("semantic_context")
        semantic_context = (
            str(semantic_context_raw).strip() if semantic_context_raw is not None else None
        )
        label_confidence = parse_label_confidence(metadata, row_index=index)
        shot = IdentifiedShot.model_validate(
            {
                "shotId": f"shot-{index:03d}",
                "startSec": start_sec,
                "endSec": end_sec,
                "vlmTag": tag,
                "keyInstantStartSec": key_instant_start,
                "dishName": dish_name or None,
                "reasoning": str(metadata.get("reasoning", "")).strip(),
                "semanticContext": semantic_context or None,
                "labelConfidence": label_confidence,
                "verifiedBy": "twelvelabs",
            }
        )
        normalized.append(sanitize_dish_name(shot))

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
        clip_media: ClipMedia | None = None,
        additional_context: ParsedReviewNotes | None = None,
    ) -> tuple[Clip, dict[str, Any]]:
        logical_source = clip_source_path if clip_source_path is not None else video_path
        media = clip_media if clip_media is not None else probe_media(logical_source)
        upload_name = twelvelabs_upload_filename(logical_source, video_path)
        asset = self._get_or_create_asset(
            video_path,
            upload_filename=upload_name,
            log_clip_name=logical_source.name,
        )
        segment_defs = segment_definitions_with_extra_context(additional_context)
        task = self.client.analyze_async.tasks.create(
            video=VideoContext_AssetId(asset_id=asset.id),
            model_name=self.model,
            analysis_mode="time_based_metadata",
            min_segment_duration=self.min_segment_duration,
            max_segment_duration=self.max_segment_duration,
            response_format=AsyncResponseFormat(
                type="segment_definitions",
                segment_definitions=segment_defs,
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
            durationSec=media.duration_sec,
            capturedAt=media.capture_metadata.captured_at,
            location=media.capture_metadata.location,
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
                existing_id = getattr(existing_asset, "id", None)
                if not existing_id:
                    raise RuntimeError(f"[{label}] Existing TwelveLabs asset is missing id")
                return self._wait_for_asset(str(existing_id))

        print(f"[{label}] Uploading video as {filename}")
        with video_path.open("rb") as video_file:
            asset = self.client.assets.create(method="direct", file=video_file, filename=filename)
        print(f"[{label}] Created TwelveLabs asset: {asset.id}")

        print(f"[{label}] Waiting for asset processing")
        created_id = getattr(asset, "id", None)
        if not created_id:
            raise RuntimeError(f"[{label}] Created TwelveLabs asset is missing id")
        return self._wait_for_asset(str(created_id))

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
