"""Edit package: shot-match LLM + deterministic assembly."""

from __future__ import annotations

from .agent_review import LitellmAgentReviewOrchestrator
from .assemble import assemble_render_plan, build_resolved_sentences, resolve_source_window
from .providers import ShotMatchOrchestrator
from .schema_render_plan import RenderBeat, RenderPlan, RenderWord
from .schema_shot_match import SentenceAssignment, ShotMatch, ShotRef
from .shot_match_llm import LitellmShotMatchOrchestrator, StaticShotMatchOrchestrator
from .vlm_shots import build_vlm_shots_for_prompt

__all__ = [
    "ShotMatchOrchestrator",
    "LitellmShotMatchOrchestrator",
    "LitellmAgentReviewOrchestrator",
    "StaticShotMatchOrchestrator",
    "ShotMatch",
    "ShotRef",
    "SentenceAssignment",
    "RenderPlan",
    "RenderBeat",
    "RenderWord",
    "build_resolved_sentences",
    "assemble_render_plan",
    "build_vlm_shots_for_prompt",
    "resolve_source_window",
]
