"""Pydantic models for VLM clip analysis output (restaurant-review taxonomy)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .restaurant_tags import RESTAURANT_VLM_TAGS


class Provider(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    model: str
    raw_response_ref: str = Field(alias="rawResponseRef")


class TwelveLabsClipRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(alias="assetId")
    task_id: str = Field(alias="taskId")


class IdentifiedShot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_id: str = Field(alias="shotId")
    start_sec: float = Field(alias="startSec")
    end_sec: float = Field(alias="endSec")
    vlm_tag: str = Field(alias="vlmTag")
    key_instant_start_sec: float = Field(
        alias="keyInstantStartSec",
        description=(
            "Key moment on the source timeline for this labeled action with the best framing and timing; "
            "must lie in [startSec, endSec]."
        ),
    )
    dish_name: str | None = Field(default=None, alias="dishName")
    reasoning: str
    semantic_context: str | None = Field(default=None, alias="semanticContext")

    @field_validator("vlm_tag")
    @classmethod
    def tag_must_be_from_dictionary(cls, value: str) -> str:
        if value not in RESTAURANT_VLM_TAGS:
            raise ValueError(f"vlmTag must be one of {RESTAURANT_VLM_TAGS}, got {value!r}")
        return value

    @model_validator(mode="after")
    def validate_key_within_shot_bounds(self) -> IdentifiedShot:
        if self.end_sec < self.start_sec:
            raise ValueError("endSec must be greater than or equal to startSec")
        if (
            self.key_instant_start_sec < self.start_sec
            or self.key_instant_start_sec > self.end_sec
        ):
            raise ValueError(
                f"keyInstantStartSec ({self.key_instant_start_sec}) must satisfy "
                f"startSec ({self.start_sec}) <= keyInstantStartSec <= endSec ({self.end_sec})"
            )
        return self


class Clip(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    source_path: str = Field(alias="sourcePath")
    original_filename: str = Field(alias="originalFilename")
    duration_sec: float | None = Field(alias="durationSec")
    captured_at: str | None = Field(alias="capturedAt")
    location: dict[str, Any] | None
    media: dict[str, Any]
    twelve_labs: TwelveLabsClipRef = Field(alias="twelveLabs")
    summary: str
    identified_shots: list[IdentifiedShot] = Field(alias="identifiedShots")


class VlmAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(alias="runId")
    analyzed_at: str = Field(alias="analyzedAt")
    provider: Provider
    clips: list[Clip]
