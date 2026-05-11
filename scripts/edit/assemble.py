"""Deterministic ShotMatch → RenderPlan (trusted; no LLM)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from collections.abc import Mapping, Sequence

from contracts import SentenceEntry, SentenceLedger, WordToken
from edit.schema_render_plan import RenderBeat, RenderPlan, RenderTheme, RenderWord
from edit.schema_shot_match import ShotMatch, ShotRef
from util.path_util import PathUtil
from vlm.schema import Clip, IdentifiedShot, VlmAnalysis

EPSILON = 1e-6


@dataclass(frozen=True)
class ResolvedShot:
    clip_ref: str
    shot_ref: str
    clip: Clip
    shot: IdentifiedShot


@dataclass(frozen=True)
class ResolvedSentence:
    sentence: SentenceEntry
    shots: list[ResolvedShot]


def _shot_map(analysis: VlmAnalysis) -> dict[tuple[str, str], tuple[Clip, IdentifiedShot]]:
    m: dict[tuple[str, str], tuple[Clip, IdentifiedShot]] = {}
    for clip in analysis.clips:
        for shot in clip.identified_shots:
            m[(clip.id, shot.shot_id)] = (clip, shot)
    return m


def resolve_source_window(
    key_instant_start_sec: float,
    shot: IdentifiedShot,
    clip: Clip,
    timeline_duration_sec: float,
) -> tuple[float, float]:
    """Build a fixed-duration source window anchored at ``key_instant_start_sec``.

    If the right edge overflows shot/clip bounds, shift the whole window left to preserve
    duration while keeping playbackRate exactly 1.
    """
    shot_start = shot.start_sec
    shot_end = shot.end_sec
    if shot_end < shot_start:
        raise ValueError("shot endSec < startSec")
    td = float(timeline_duration_sec)
    if td <= 0:
        raise ValueError("timeline_duration_sec must be positive")
    shot_lo = max(0.0, shot_start)
    clip_hi = float(clip.duration_sec) if clip.duration_sec is not None else float("inf")
    hi = min(shot_end, clip_hi)
    if hi <= shot_lo:
        raise ValueError(f"cannot form window for clip {clip.id} shot {shot.shot_id}")
    max_duration = hi - shot_lo
    if td > max_duration + EPSILON:
        raise ValueError(
            f"cannot allocate {td:.3f}s in clip {clip.id} shot {shot.shot_id} "
            f"(available {max_duration:.3f}s)"
        )

    s = key_instant_start_sec
    e = key_instant_start_sec + td

    if e > hi:
        shift = e - hi
        s -= shift
        e -= shift
    if s < shot_lo:
        shift = shot_lo - s
        s += shift
        e += shift

    if s < shot_lo - EPSILON or e > hi + EPSILON:
        raise ValueError(f"cannot fit source window for clip {clip.id} shot {shot.shot_id}")
    if e - s <= 0:
        raise ValueError(f"cannot form positive window for clip {clip.id} shot {shot.shot_id}")
    return s, e


def _validate_sentence_ledger(
    *,
    sentence_ledger: SentenceLedger,
    audio_duration_sec: float,
) -> None:
    if audio_duration_sec <= 0:
        raise ValueError("audio_duration_sec must be positive")
    ordered = sorted(sentence_ledger.sentences, key=lambda row: row.speech_start_sec)
    if not ordered:
        raise ValueError("sentence ledger must not be empty")
    first_start = ordered[0].speech_start_sec
    if abs(first_start - 0.0) > EPSILON:
        raise ValueError(f"first sentence must start at 0, got {first_start:.6f}")
    for idx in range(1, len(ordered)):
        prev = ordered[idx - 1]
        curr = ordered[idx]
        if abs(curr.speech_start_sec - prev.speech_end_sec) > EPSILON:
            raise ValueError(
                "sentence ledger must be contiguous: "
                f"{prev.sentence_id} ends at {prev.speech_end_sec:.6f}, "
                f"but {curr.sentence_id} starts at {curr.speech_start_sec:.6f}"
            )
    last_end = ordered[-1].speech_end_sec
    if abs(last_end - audio_duration_sec) > EPSILON:
        raise ValueError(
            f"last sentence must end at audio duration: {last_end:.6f} vs {audio_duration_sec:.6f}"
        )


def build_resolved_sentences(
    *,
    shot_match: ShotMatch,
    analysis: VlmAnalysis,
    sentence_ledger: SentenceLedger,
    audio_duration_sec: float,
) -> list[ResolvedSentence]:
    """Return ordered, validated resolved sentence rows used by plan assembly."""
    _validate_sentence_ledger(sentence_ledger=sentence_ledger, audio_duration_sec=audio_duration_sec)
    shots_by_ref = _shot_map(analysis)
    assignment_by_sentence: Mapping[str, Sequence[ShotRef]] = {
        row.sentence_id: list(row.shots) for row in shot_match.assignments
    }

    ledger_sentences = {(row.sentence_id, row.text.strip()) for row in sentence_ledger.sentences}
    shot_sentences = {(row.sentence_id, row.text.strip()) for row in shot_match.assignments}
    if ledger_sentences != shot_sentences:
        raise ValueError(
            "shot-match sentences do not match ledger (ids or trimmed text differ): "
            f"only in ledger {sorted(ledger_sentences - shot_sentences)!r}; "
            f"only in shot-match {sorted(shot_sentences - ledger_sentences)!r}"
        )

    ordered = sorted(sentence_ledger.sentences, key=lambda row: row.speech_start_sec)
    resolved: list[ResolvedSentence] = []
    for sentence in ordered:
        sid = sentence.sentence_id
        shots_assignment = assignment_by_sentence.get(sid)
        if shots_assignment is None:
            raise ValueError(f"missing assignments for sentence {sid!r}")
        beat_expected = sentence.beat_count
        if len(shots_assignment) != beat_expected:
            raise ValueError(
                f"sentence {sid!r}: expected {beat_expected} shots, got {len(shots_assignment)}"
            )
        resolved_shots: list[ResolvedShot] = []
        for shot_ref in shots_assignment:
            resolved_row = shots_by_ref.get((shot_ref.clip_id, shot_ref.shot_id))
            if resolved_row is None:
                raise ValueError(
                    f"unknown shot clip={shot_ref.clip_id!r} shot={shot_ref.shot_id!r}"
                )
            clip_obj, identified_shot = resolved_row
            resolved_shots.append(
                ResolvedShot(
                    clip_ref=shot_ref.clip_id,
                    shot_ref=shot_ref.shot_id,
                    clip=clip_obj,
                    shot=identified_shot,
                )
            )
        resolved.append(ResolvedSentence(sentence=sentence, shots=resolved_shots))
    return resolved


def assemble_render_plan(
    resolved_sentences: Sequence[ResolvedSentence],
    whisper_words: Sequence[WordToken],
    voiceover_static_path: str,
    audio_duration_sec: float,
    run_id: str,
    created_at: str,
    hook_text: str | None = None,
    paths: PathUtil | None = None,
) -> RenderPlan:
    """Build RenderPlan + validate beats / assignments / lengths.

    When ``paths`` is set, writes ``render-plan.json`` under the run directory.
    """
    warnings: list[str] = []
    beats_out: list[RenderBeat] = []
    prev_pair: tuple[str, str] | None = None
    timeline_cursor = 0.0

    for resolved_sentence in resolved_sentences:
        sentence = resolved_sentence.sentence
        sid = sentence.sentence_id
        sentence_duration = sentence.speech_end_sec - sentence.speech_start_sec
        if sentence_duration <= 0:
            raise ValueError(f"non-positive sentence duration for {sid}")
        beat_expected = sentence.beat_count
        allocated_shot_time = sentence_duration / float(beat_expected)
        if allocated_shot_time <= 0:
            raise ValueError(f"non-positive allocated shot duration for {sid}")

        for j, resolved_shot in enumerate(resolved_sentence.shots):
            timeline_start = timeline_cursor
            timeline_end = timeline_start + allocated_shot_time
            timeline_cursor = timeline_end
            source_start, source_end = resolve_source_window(
                resolved_shot.shot.key_instant_start_sec,
                resolved_shot.shot,
                resolved_shot.clip,
                allocated_shot_time,
            )

            pair = (resolved_shot.clip_ref, resolved_shot.shot_ref)
            if prev_pair is not None and pair == prev_pair:
                warnings.append(
                    f"consecutive beats reuse same footage {pair} "
                    f"(sentence {sentence.sentence_id} beat {j})"
                )
            prev_pair = pair

            beats_out.append(
                RenderBeat(
                    beatId=f"{sid}-{j}",
                    sentenceId=sid,
                    clipId=resolved_shot.clip_ref,
                    shotId=resolved_shot.shot_ref,
                    sourcePath=resolved_shot.clip.source_path,
                    sourceStartSec=source_start,
                    sourceEndSec=source_end,
                    timelineStartSec=timeline_start,
                    timelineEndSec=timeline_end,
                    playbackRate=1.0,
                )
            )

    words_render = [
        RenderWord(word=w.word, startSec=w.start_sec, endSec=w.end_sec) for w in whisper_words
    ]
    hook = (
        hook_text.strip()
        if hook_text
        else (resolved_sentences[0].sentence.text.strip() if resolved_sentences else "Short")
    )
    if beats_out and abs(beats_out[-1].timeline_end_sec - audio_duration_sec) > EPSILON:
        raise ValueError(
            "assembled beats must end at audio duration: "
            f"{beats_out[-1].timeline_end_sec:.6f} vs {audio_duration_sec:.6f}"
        )

    plan = RenderPlan(
        runId=run_id,
        createdAt=created_at,
        durationSec=audio_duration_sec,
        voiceoverStaticPath=voiceover_static_path,
        theme=RenderTheme(hookText=hook),
        beats=sorted(beats_out, key=lambda b: (b.timeline_start_sec, b.beat_id)),
        words=words_render,
        warnings=warnings,
    )
    if paths is not None:
        plan_path = paths.render_plan_json()
        plan_dump = plan.model_dump(by_alias=True)
        plan_path.write_text(json.dumps(plan_dump, indent=2, ensure_ascii=False) + "\n")
        print(f"Wrote render plan: {plan_path}")
    return plan
