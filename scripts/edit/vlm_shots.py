"""Compact VLM rows for prompt context (ids + taxonomy only)."""

from __future__ import annotations

from typing import Any

from vlm.schema import IdentifiedShot, VlmAnalysis


def build_vlm_shots_for_prompt(analysis: VlmAnalysis) -> list[dict[str, Any]]:
    """Flat list for orchestration prompts (no filesystem paths)."""
    rows: list[dict[str, Any]] = []
    for clip in analysis.clips:
        for shot in clip.identified_shots:
            row = {
                "clipId": clip.id,
                "shotId": shot.shot_id,
                "vlmTag": shot.vlm_tag,
                "reasoning": shot.reasoning,
            }
            if shot.dish_name:
                row["dishName"] = shot.dish_name
            rows.append(row)
    return rows
