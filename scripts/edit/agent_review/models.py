"""Data models used by agent-review tools and orchestrator."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from contracts import SentenceLedger, WordToken
from edit.schema_shot_match import SentenceAssignment
from vlm.schema import VlmAnalysis


class ClipReview(BaseModel):
    """Clip-level pass/fail decision emitted by review step."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    sentence_id: str = Field(alias="sentenceId")
    clip_id: str = Field(alias="clipId")
    shot_id: str = Field(alias="shotId")
    passed: bool
    feedback: str


class ReviewRenderResult(BaseModel):
    """Return contract for ``review_render`` tool."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    passed: bool
    clip_reviews: list[ClipReview] = Field(default_factory=list, alias="clipReviews")
    suggested_assignments: list[SentenceAssignment] = Field(default_factory=list, alias="suggestedAssignments")


@dataclass
class AgentReviewInputs:
    analysis: VlmAnalysis
    ledger: SentenceLedger
    words: list[WordToken]
    voiceover_static_path: str
    audio_duration_sec: float
    hook_text: str

