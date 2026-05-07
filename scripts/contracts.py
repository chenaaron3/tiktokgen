"""Shared DTOs between narrative and edit (no external service imports)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WordToken(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    word: str
    start_sec: float = Field(ge=0.0, alias="startSec")
    end_sec: float = Field(ge=0.0, alias="endSec")

    @model_validator(mode="after")
    def ends_after_start(self) -> "WordToken":
        if self.end_sec < self.start_sec:
            raise ValueError("endSec must be >= startSec")
        return self


class SentenceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    sentence_id: str = Field(alias="sentenceId")
    text: str
    speech_start_sec: float = Field(ge=0.0, alias="speechStartSec")
    speech_end_sec: float = Field(ge=0.0, alias="speechEndSec")
    beat_count: int = Field(ge=1, alias="beatCount")

    @model_validator(mode="after")
    def validate_window(self) -> "SentenceEntry":
        if self.speech_end_sec < self.speech_start_sec:
            raise ValueError("speechEndSec must be >= speechStartSec")
        return self


class SentenceLedger(BaseModel):
    """Deterministic sentence timings and beat counts (input to shot-match LLM)."""

    model_config = ConfigDict(extra="forbid")

    sentences: list[SentenceEntry]
