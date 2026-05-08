"""Edit package: shot-match LLM + deterministic assembly."""

from __future__ import annotations

from .assemble import assemble_render_plan, resolve_source_window, validate_shots
from .providers import ShotMatchOrchestrator
from .schema_render_plan import RenderBeat, RenderPlan, RenderWord
from .schema_shot_match import SentenceAssignment, ShotMatch, ShotRef
from .shot_match_llm import LitellmShotMatchOrchestrator, StaticShotMatchOrchestrator
from .vlm_shots import build_vlm_shots_for_prompt

__all__ = [
    "ShotMatchOrchestrator",
    "LitellmShotMatchOrchestrator",
    "StaticShotMatchOrchestrator",
    "ShotMatch",
    "ShotRef",
    "SentenceAssignment",
    "RenderPlan",
    "RenderBeat",
    "RenderWord",
    "assemble_render_plan",
    "validate_shots",
    "build_vlm_shots_for_prompt",
    "resolve_source_window",
]
