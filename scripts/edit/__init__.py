"""Edit package: shot-match LLM + deterministic assembly."""

from __future__ import annotations

from .assemble import assemble_render_plan, resolve_source_window
from .providers import ShotMatchOrchestrator
from .schema_render_plan import RenderBeat, RenderPlan, RenderWord
from .schema_shot_match import SentenceAssignment, ShotMatch, ShotRef, ShotSentenceLine
from .shot_match_llm import LitellmShotMatchOrchestrator, StaticShotMatchOrchestrator
from .vlm_shots import build_vlm_shots_for_prompt

__all__ = [
    "ShotMatchOrchestrator",
    "LitellmShotMatchOrchestrator",
    "StaticShotMatchOrchestrator",
    "ShotMatch",
    "ShotRef",
    "ShotSentenceLine",
    "SentenceAssignment",
    "RenderPlan",
    "RenderBeat",
    "RenderWord",
    "assemble_render_plan",
    "build_vlm_shots_for_prompt",
    "resolve_source_window",
]
