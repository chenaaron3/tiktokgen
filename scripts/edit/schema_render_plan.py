"""Fully resolved Remotion-facing plan (trusted deterministic assembly)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RenderWord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    word: str
    start_sec: float = Field(ge=0.0, alias="startSec")
    end_sec: float = Field(ge=0.0, alias="endSec")


class RenderBeat(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    beat_id: str = Field(alias="beatId")
    sentence_id: str = Field(alias="sentenceId")
    clip_id: str = Field(alias="clipId")
    shot_id: str = Field(alias="shotId")
    source_path: str = Field(alias="sourcePath")
    source_start_sec: float = Field(ge=0.0, alias="sourceStartSec")
    source_end_sec: float = Field(ge=0.0, alias="sourceEndSec")
    timeline_start_sec: float = Field(ge=0.0, alias="timelineStartSec")
    timeline_end_sec: float = Field(ge=0.0, alias="timelineEndSec")
    playback_rate: float = Field(gt=0.0, alias="playbackRate")


class RenderTheme(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    hook_text: str = Field(alias="hookText")


class RenderPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    run_id: str = Field(alias="runId")
    created_at: str = Field(alias="createdAt")
    duration_sec: float = Field(gt=0.0, alias="durationSec")
    voiceover_static_path: str = Field(
        alias="voiceoverStaticPath",
        description="Path relative to remotion/public, e.g. render-assets/xyz/voice.mp3",
    )
    theme: RenderTheme | None = None
    beats: list[RenderBeat]
    words: list[RenderWord]
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
