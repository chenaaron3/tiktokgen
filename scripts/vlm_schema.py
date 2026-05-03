"""Pydantic models for generic VLM clip analysis output."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Provider(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    model: str
    raw_response_ref: str = Field(alias="rawResponseRef")


class TwelveLabsClipRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(alias="assetId")
    task_id: str = Field(alias="taskId")


class Moment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    moment_id: str = Field(alias="momentId")
    start_sec: float = Field(alias="startSec")
    end_sec: float = Field(alias="endSec")
    description: str
    subjects: list[str]
    actions: list[str]
    visible_text: list[str] = Field(alias="visibleText")
    spoken_text: str = Field(alias="spokenText")
    audio: list[str]
    quality: Literal["great", "good", "okay", "poor"]
    issues: list[str]
    why_useful: str = Field(alias="whyUseful")


class Clip(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source_path: str = Field(alias="sourcePath")
    original_filename: str = Field(alias="originalFilename")
    duration_sec: float | None = Field(alias="durationSec")
    captured_at: str | None = Field(alias="capturedAt")
    location: dict[str, Any] | None
    media: dict[str, Any]
    twelve_labs: TwelveLabsClipRef = Field(alias="twelveLabs")
    summary: str
    moments: list[Moment]


class VlmAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.3.0"] = Field(alias="schemaVersion")
    run_id: str = Field(alias="runId")
    analyzed_at: str = Field(alias="analyzedAt")
    provider: Provider
    clips: list[Clip]
