"""Runtime context shared by agent-review tools."""

from __future__ import annotations

from dataclasses import dataclass

from edit.agent_review.models import AgentReviewInputs
from edit.schema_shot_match import ShotMatch
from util import PathUtil


@dataclass
class ToolRuntimeContext:
    paths: PathUtil
    inputs: AgentReviewInputs
    plan_version: int
    shot_match: ShotMatch
    latest_pass: bool
    last_review_result: dict[str, Any] | None
    passed_sentence_ids: set[str]

    @classmethod
    def create(
        cls,
        *,
        paths: PathUtil,
        inputs: AgentReviewInputs,
        shot_match: ShotMatch,
    ) -> "ToolRuntimeContext":
        return cls(
            paths=paths,
            inputs=inputs,
            plan_version=1,
            shot_match=shot_match.model_copy(deep=True),
            latest_pass=False,
            last_review_result=None,
            passed_sentence_ids=set(),
        )

