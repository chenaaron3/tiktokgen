"""Shot match → render plan (facade over resolve + build modules)."""

from __future__ import annotations

from edit.build_render_plan import assemble_render_plan, resolve_source_window
from edit.resolve_shot_match import (
    ResolvedSentence,
    ResolvedShot,
    build_resolved_sentences,
)

__all__ = [
    "ResolvedShot",
    "ResolvedSentence",
    "build_resolved_sentences",
    "assemble_render_plan",
    "resolve_source_window",
]
