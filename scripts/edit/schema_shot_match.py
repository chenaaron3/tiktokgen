"""Minimal LLM / human-readable shot assignment (ShotMatch artifact)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ShotRef(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    clip_id: str = Field(alias="clipId")
    shot_id: str = Field(alias="shotId")
    beat_span: int = Field(ge=1, le=2, alias="beatSpan")
    reasoning: str


class SentenceAssignment(BaseModel):
    """One narration sentence plus its ordered b-roll picks."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    sentence_id: str = Field(alias="sentenceId")
    text: str
    shots: list[ShotRef]


class ShotMatch(BaseModel):
    """Reviewable editorial output; assemble turns this into RenderPlan."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    planning: str = Field(alias="_planning")
    assignments: list[SentenceAssignment]

    @model_validator(mode="after")
    def _unique_sentence_ids(self) -> ShotMatch:
        ids = [a.sentence_id for a in self.assignments]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate sentenceId in ShotMatch.assignments")
        return self
