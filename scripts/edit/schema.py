"""Pydantic models for minimal Remotion edit-plan output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Theme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    hook_text: str = Field(alias="hookText")


class LocationSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    role: Literal["opening", "setup", "main", "texture", "ending"]
    summary: str
    latitude: float | None = None
    longitude: float | None = None
    timeline_start_sec: float = Field(alias="timelineStartSec")
    timeline_end_sec: float = Field(alias="timelineEndSec")
    segment_ids: list[str] = Field(alias="segmentIds")

    @model_validator(mode="after")
    def validate_timeline(self) -> "LocationSection":
        if self.timeline_end_sec <= self.timeline_start_sec:
            raise ValueError("timelineEndSec must be greater than timelineStartSec")
        if not self.segment_ids:
            raise ValueError("locations must reference at least one segment")
        return self


class Crop(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    scale: float = Field(ge=1.0)


class Segment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    location_id: str = Field(alias="locationId")
    clip_id: str = Field(alias="clipId")
    moment_id: str | None = Field(alias="momentId", default=None)
    source_path: str = Field(alias="sourcePath")
    source_start_sec: float = Field(alias="sourceStartSec", ge=0.0)
    source_end_sec: float = Field(alias="sourceEndSec", ge=0.0)
    timeline_start_sec: float = Field(alias="timelineStartSec", ge=0.0)
    timeline_end_sec: float = Field(alias="timelineEndSec", ge=0.0)
    role: Literal[
        "hook",
        "setup",
        "context",
        "signature",
        "detail",
        "texture",
        "ambience",
        "transition",
        "payoff",
        "ending",
    ]
    visual_type: Literal[
        "closeup",
        "wide",
        "detail",
        "action",
        "people",
        "sign",
        "pov",
        "food",
        "storefront",
        "ambience",
    ] = Field(alias="visualType")
    pacing: Literal["fast", "medium", "hold"]
    label: str
    crop: Crop
    reason: str

    @model_validator(mode="after")
    def validate_ranges(self) -> "Segment":
        if self.source_end_sec <= self.source_start_sec:
            raise ValueError("sourceEndSec must be greater than sourceStartSec")
        if self.timeline_end_sec <= self.timeline_start_sec:
            raise ValueError("timelineEndSec must be greater than timelineStartSec")
        return self


class TextOverlay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    timeline_start_sec: float = Field(alias="timelineStartSec", ge=0.0)
    timeline_end_sec: float = Field(alias="timelineEndSec", ge=0.0)
    position: Literal["top", "center", "bottom"]

    @model_validator(mode="after")
    def validate_timeline(self) -> "TextOverlay":
        if self.timeline_end_sec <= self.timeline_start_sec:
            raise ValueError("timelineEndSec must be greater than timelineStartSec")
        return self


class EditPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.1.0"] = Field(alias="schemaVersion")
    run_id: str = Field(alias="runId")
    source_analysis_ref: str = Field(alias="sourceAnalysisRef")
    created_at: str = Field(alias="createdAt")
    guidance: str
    theme: Theme
    duration_sec: float = Field(alias="durationSec", gt=0.0)
    locations: list[LocationSection]
    segments: list[Segment]
    text: list[TextOverlay]
    assumptions: list[str]
    warnings: list[str]

    @model_validator(mode="after")
    def validate_plan_links(self) -> "EditPlan":
        location_ids = {location.id for location in self.locations}
        segment_ids = {segment.id for segment in self.segments}

        for segment in self.segments:
            if segment.location_id not in location_ids:
                raise ValueError(f"segment {segment.id} references missing locationId {segment.location_id}")
            if segment.timeline_end_sec > self.duration_sec:
                raise ValueError(f"segment {segment.id} exceeds durationSec")

        for location in self.locations:
            missing = [segment_id for segment_id in location.segment_ids if segment_id not in segment_ids]
            if missing:
                raise ValueError(f"location {location.id} references missing segmentIds: {missing}")
            if location.timeline_end_sec > self.duration_sec:
                raise ValueError(f"location {location.id} exceeds durationSec")

        for overlay in self.text:
            if overlay.timeline_end_sec > self.duration_sec:
                raise ValueError(f"text overlay {overlay.id} exceeds durationSec")

        ordered_segments = sorted(self.segments, key=lambda segment: segment.timeline_start_sec)
        if ordered_segments and ordered_segments[0].role != "hook":
            raise ValueError("the first segment must have role 'hook'")

        return self
