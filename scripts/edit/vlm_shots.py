"""Markdown context for the shot-match LLM (narration + shot catalog)."""

from __future__ import annotations

from contracts import SentenceLedger
from vlm.schema import IdentifiedShot, VlmAnalysis


def format_sentences_markdown(ledger: SentenceLedger) -> str:
    """Build ordered narration lines with beat counts and speech timing."""
    parts = ["# Narration", ""]
    for index, sentence in enumerate(ledger.sentences):
        heading = sentence.sentence_id
        if index == 0:
            heading = f"{sentence.sentence_id} (hook)"
        parts.extend(
            [
                f"### {heading}",
                f"- text: {sentence.text.strip()}",
                f"- beatCount: {sentence.beat_count}",
                (
                    f"- speech: {sentence.speech_start_sec:.1f}s"
                    f" – {sentence.speech_end_sec:.1f}s"
                ),
                "",
            ]
        )
    return "\n".join(parts).strip() + "\n"


def format_shot_match_user_message(*, ledger: SentenceLedger, analysis: VlmAnalysis) -> str:
    return f"{format_sentences_markdown(ledger)}\n\n{format_vlm_shots_markdown(analysis)}"


def _shot_markdown_block(clip_id: str, shot: IdentifiedShot) -> str:
    lines = [
        f"### {clip_id} / {shot.shot_id}",
        f"- tag: {shot.vlm_tag}",
        f"- reasoning: {shot.reasoning.strip()}",
    ]
    return "\n".join(lines)


def format_vlm_shots_markdown(analysis: VlmAnalysis) -> str:
    """Build a markdown shot catalog for the shot-match LLM (excludes ``not_suitable``)."""
    general: list[str] = []
    by_dish: dict[str, list[str]] = {}

    for clip in analysis.clips:
        for shot in clip.identified_shots:
            if shot.vlm_tag == "not_suitable":
                continue
            block = _shot_markdown_block(clip.id, shot)
            dish = (shot.dish_name or "").strip()
            if dish:
                by_dish.setdefault(dish, []).append(block)
            else:
                general.append(block)

    parts = ["# Shot catalog", "## General shots"]
    if general:
        parts.append("\n\n".join(general))
    else:
        parts.append("_No general shots._")

    for dish_name in sorted(by_dish.keys(), key=lambda name: name.casefold()):
        parts.extend(["", f"## Dish: {dish_name}", ""])
        parts.append("\n\n".join(by_dish[dish_name]))

    return "\n".join(parts).strip() + "\n"
