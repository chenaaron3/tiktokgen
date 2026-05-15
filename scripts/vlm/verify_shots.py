"""GPT vision verification for low/medium-confidence TwelveLabs shot labels."""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from typing import Any, Literal

import litellm
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator

from edit.strict_json import make_openai_strict_schema
from logger import install_local_observability_logger
from util.path_util import PathUtil
from vlm.frame_extract import extract_frame_jpeg, sample_shot_timestamps_sec
from vlm.notes import ParsedReviewNotes
from vlm.restaurant_tags import RESTAURANT_VLM_TAGS
from vlm.schema import Clip, IdentifiedShot
from vlm.shot_labels import sanitize_dish_name

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VERIFY_SYSTEM_PROMPT = (PROJECT_ROOT / "prompts" / "vlm_shot_verifier.md").read_text(encoding="utf-8")
DEFAULT_VERIFY_MODEL = "openai/gpt-4.1-mini"


class GptShotVerification(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    vlm_tag: str = Field(alias="vlmTag")
    dish_name: str = Field(default="", alias="dishName")
    reasoning: str
    semantic_context: str = Field(default="", alias="semanticContext")
    label_confidence: Literal["low", "medium", "high"] = Field(alias="labelConfidence")

    @field_validator("vlm_tag")
    @classmethod
    def tag_must_be_valid(cls, value: str) -> str:
        if value not in RESTAURANT_VLM_TAGS:
            raise ValueError(f"vlmTag must be one of {RESTAURANT_VLM_TAGS}, got {value!r}")
        return value

    @field_validator("label_confidence")
    @classmethod
    def confidence_must_be_valid(cls, value: str) -> str:
        if value not in ("low", "medium", "high"):
            raise ValueError(f"labelConfidence must be low, medium, or high, got {value!r}")
        return value


def _allowed_dishes_from_notes(
    notes: ParsedReviewNotes | None,
) -> list[dict[str, str]]:
    if notes is None:
        return []
    return [{"name": dish.name, "description": dish.description} for dish in notes.dishes]


def _allowed_dish_names(allowed_dishes: list[dict[str, str]]) -> list[str]:
    return [dish["name"] for dish in allowed_dishes]


def _needs_gpt_verification(shot: IdentifiedShot) -> bool:
    return shot.label_confidence in ("low", "medium")


def _encode_image_data_url(path: Path) -> str:
    payload = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{payload}"


def _build_verify_user_content(
    *,
    allowed_dishes: list[dict[str, str]],
    frame_samples: list[tuple[float, Path]],
) -> list[dict[str, Any]]:
    """Constraints JSON, then each frame preceded by its clip timeline timestamp."""
    constraints = json.dumps(
        {
            "allowedVlmTags": list(RESTAURANT_VLM_TAGS),
            "allowedDishes": allowed_dishes,
        },
        ensure_ascii=False,
        indent=2,
    )
    content: list[dict[str, Any]] = [{"type": "text", "text": constraints}]
    for timestamp_sec, frame_path in frame_samples:
        content.append(
            {
                "type": "text",
                "text": f"Frame at {timestamp_sec:.1f}s on the source clip timeline:",
            }
        )
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": _encode_image_data_url(frame_path)},
            }
        )
    return content


def _verify_shot_with_gpt(
    *,
    shot: IdentifiedShot,
    frame_samples: list[tuple[float, Path]],
    allowed_dishes: list[dict[str, str]],
    model: str,
    observability_path: Path | None,
) -> IdentifiedShot:
    schema = make_openai_strict_schema(GptShotVerification.model_json_schema(by_alias=True))
    response_format = {
        "type": "json_schema",
        "json_schema": {"name": "shot_verification", "schema": schema, "strict": True},
    }
    content = _build_verify_user_content(
        allowed_dishes=allowed_dishes,
        frame_samples=frame_samples,
    )

    metadata: dict[str, Any] | None = None
    if observability_path is not None:
        metadata = {"stage": "vlm_verify", "observabilityPath": str(observability_path)}

    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": VERIFY_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        response_format=response_format,
        metadata=metadata,
    )
    raw = response.choices[0].message.content
    if not raw:
        raise RuntimeError("GPT shot verification returned empty content")
    verified = GptShotVerification.model_validate(json.loads(raw))
    allowed_dish_names = _allowed_dish_names(allowed_dishes)
    dish_name = verified.dish_name.strip() or None
    if dish_name and allowed_dish_names and dish_name not in allowed_dish_names:
        print(
            f"Warning: GPT dish {dish_name!r} not in notes dish list "
            f"{allowed_dish_names!r}; clearing dishName for {shot.shot_id}.",
            file=sys.stderr,
        )
        dish_name = None
    semantic_context = verified.semantic_context.strip() or None
    return IdentifiedShot.model_validate(
        {
            "shotId": shot.shot_id,
            "startSec": shot.start_sec,
            "endSec": shot.end_sec,
            "vlmTag": verified.vlm_tag,
            "keyInstantStartSec": shot.key_instant_start_sec,
            "dishName": dish_name,
            "reasoning": verified.reasoning.strip(),
            "semanticContext": semantic_context,
            "labelConfidence": verified.label_confidence,
            "verifiedBy": "gpt",
        }
    )


def _clip_duration_sec(clip: Clip) -> float | None:
    for candidate in (clip.duration_sec, clip.media.duration_sec):
        if isinstance(candidate, (int, float)) and candidate > 0:
            return float(candidate)
    return None


def verify_clip_shots(
    clip: Clip,
    *,
    notes: ParsedReviewNotes | None,
    paths: PathUtil,
    model: str = DEFAULT_VERIFY_MODEL,
) -> Clip:
    video_path = Path(clip.source_path)
    if not video_path.is_file():
        raise FileNotFoundError(f"Cannot verify shots; missing clip video: {video_path}")

    clip_duration = _clip_duration_sec(clip)
    allowed_dishes = _allowed_dishes_from_notes(notes)
    frames_dir = paths.vlm_verify_frames_dir()
    verified_shots: list[IdentifiedShot] = []
    for shot in clip.identified_shots:
        sanitized = sanitize_dish_name(shot)
        if not _needs_gpt_verification(sanitized):
            verified_shots.append(sanitized)
            continue

        timestamps = sample_shot_timestamps_sec(
            sanitized.start_sec,
            sanitized.end_sec,
            clip_duration_sec=clip_duration,
        )
        frame_samples: list[tuple[float, Path]] = []
        shot_frames_dir = frames_dir / f"{clip.id}__{sanitized.shot_id}"
        for index, timestamp in enumerate(timestamps):
            frame_path = extract_frame_jpeg(
                video_path,
                timestamp,
                shot_frames_dir / f"frame-{index:02d}-{int(timestamp)}s.jpg",
            )
            frame_samples.append((timestamp, frame_path))

        obs_path = paths.vlm_verify_llm_observability_json(clip.id, sanitized.shot_id)

        print(
            f"[{clip.id}] GPT verify {sanitized.shot_id} "
            f"({sanitized.label_confidence}, {len(frame_samples)} frame(s))"
        )
        verified_shots.append(
            _verify_shot_with_gpt(
                shot=sanitized,
                frame_samples=frame_samples,
                allowed_dishes=allowed_dishes,
                model=model,
                observability_path=obs_path,
            )
        )

    return clip.model_copy(update={"identified_shots": verified_shots})


def verify_analysis_clips(
    clips: list[Clip],
    *,
    notes: ParsedReviewNotes | None,
    paths: PathUtil,
    model: str | None = None,
) -> list[Clip]:
    """Run GPT verification for shots that need it; accept high-confidence labels as-is."""
    load_dotenv(PROJECT_ROOT / ".env")
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for GPT shot verification")

    install_local_observability_logger()
    resolved_model = model or os.environ.get("VLM_VERIFY_MODEL", DEFAULT_VERIFY_MODEL)

    verified: list[Clip] = []
    for clip in clips:
        verified.append(
            verify_clip_shots(
                clip,
                notes=notes,
                paths=paths,
                model=resolved_model,
            )
        )
    return verified
