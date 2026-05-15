"""Edit package: shot-match LLM + deterministic assembly."""

from __future__ import annotations

from .assemble import assemble_render_plan, build_resolved_sentences, resolve_source_window
from .providers import ShotMatchOrchestrator
from .schema_render_plan import RenderBeat, RenderPlan, RenderWord
from .schema_shot_match import SentenceAssignment, ShotMatch, ShotRef
from .shot_match_llm import LitellmShotMatchOrchestrator, StaticShotMatchOrchestrator
from .vlm_shots import (
    format_sentences_markdown,
    format_shot_match_user_message,
    format_vlm_shots_markdown,
)

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
    "build_resolved_sentences",
    "assemble_render_plan",
    "format_sentences_markdown",
    "format_vlm_shots_markdown",
    "format_shot_match_user_message",
    "resolve_source_window",
]
