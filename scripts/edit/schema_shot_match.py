"""Minimal LLM / human-readable shot assignment (ShotMatch artifact)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ShotSentenceLine(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    sentence_id: str = Field(alias="sentenceId")
    text: str


class ShotRef(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    clip_id: str = Field(alias="clipId")
    moment_id: str = Field(alias="momentId")


class SentenceAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    sentence_id: str = Field(alias="sentenceId")
    shots: list[ShotRef]


class ShotMatch(BaseModel):
    """Reviewable editorial output; assemble turns this into RenderPlan."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal["0.2.0"] = Field(alias="schemaVersion")
    sentences: list[ShotSentenceLine]
    assignments: list[SentenceAssignment]
