"""Deterministic ShotMatch → RenderPlan (trusted; no LLM)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from contracts import SentenceLedger, WordToken
from edit.schema_render_plan import RenderBeat, RenderPlan, RenderTheme, RenderWord
from edit.schema_shot_match import ShotMatch, ShotRef
from vlm.schema import Clip, IdentifiedShot, VlmAnalysis


def _moment_map(analysis: VlmAnalysis) -> dict[tuple[str, str], tuple[Clip, IdentifiedShot]]:
    m: dict[tuple[str, str], tuple[Clip, IdentifiedShot]] = {}
    for clip in analysis.clips:
        for shot in clip.identified_shots:
            m[(clip.id, shot.moment_id)] = (clip, shot)
    return m


def resolve_source_window(
    key_instant_sec: float,
    shot: IdentifiedShot,
    clip: Clip,
    timeline_duration_sec: float,
) -> tuple[float, float]:
    """Trim source around ``keyInstant`` long enough for this beat's timeline duration.

    Window length is ``min(timeline_duration_sec, shot_span)`` (never longer than the
    identified shot), then clamped to the clip file bounds. Playback rate stays ~1 when
    the shot has enough contiguous span to cover the full beat."""
    shot_start = shot.start_sec
    shot_end = shot.end_sec
    if shot_end < shot_start:
        raise ValueError("shot endSec < startSec")
    span = shot_end - shot_start
    if span <= 0:
        raise ValueError("invalid shot span")

    duration_limit = clip.duration_sec
    dur_file = float(duration_limit) if duration_limit is not None else float("inf")

    td = float(timeline_duration_sec)
    if td <= 0:
        raise ValueError("timeline_duration_sec must be positive")
    want_duration = min(td, span)
    lo = shot_start
    hi = shot_end - want_duration
    if hi < lo:
        hi = lo
    centered = max(lo, min(key_instant_sec - want_duration / 2.0, hi))
    s = centered
    e = centered + want_duration
    if e > dur_file:
        shift = e - dur_file
        s = max(shot_start, s - shift)
        e = dur_file
    if s < 0:
        adj = -s
        s = 0.0
        e = min(dur_file, e + adj)
    if e - s <= 0:
        raise ValueError(f"cannot form window for clip {clip.id} moment {shot.moment_id}")
    return s, e


def validate_shots(
    *,
    shot_match: ShotMatch,
    sentence_ledger: SentenceLedger,
    moments: Mapping[tuple[str, str], tuple[Clip, IdentifiedShot]],
    assignment_by_sentence: Mapping[str, Sequence[ShotRef]],
) -> None:
    """Raise ``ValueError`` if shot-match disagrees with the ledger or references unknown VLM shots."""
    ledger_sentences = {(row.sentence_id, row.text.strip()) for row in sentence_ledger.sentences}
    shot_sentences = {(row.sentence_id, row.text.strip()) for row in shot_match.assignments}
    if ledger_sentences != shot_sentences:
        raise ValueError(
            "shot-match sentences do not match ledger (ids or trimmed text differ): "
            f"only in ledger {sorted(ledger_sentences - shot_sentences)!r}; "
            f"only in shot-match {sorted(shot_sentences - ledger_sentences)!r}"
        )

    ordered = sorted(sentence_ledger.sentences, key=lambda row: row.speech_start_sec)
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
        for shot_ref in shots_assignment:
            if moments.get((shot_ref.clip_id, shot_ref.moment_id)) is None:
                raise ValueError(
                    f"unknown shot clip={shot_ref.clip_id!r} moment={shot_ref.moment_id!r}"
                )


def assemble_render_plan(
    *,
    shot_match: ShotMatch,
    analysis: VlmAnalysis,
    sentence_ledger: SentenceLedger,
    whisper_words: Sequence[WordToken],
    voiceover_static_path: str,
    audio_duration_sec: float,
    run_id: str,
    created_at: str,
    hook_text: str | None = None,
) -> RenderPlan:
    """Build RenderPlan + validate beats / assignments / lengths."""
    moments = _moment_map(analysis)
    # Maps sentence ID to list of shots
    assignment_by_sentence: Mapping[str, list[ShotRef]] = {
        row.sentence_id: list(row.shots) for row in shot_match.assignments
    }

    validate_shots(
        shot_match=shot_match,
        sentence_ledger=sentence_ledger,
        moments=moments,
        assignment_by_sentence=assignment_by_sentence,
    )

    warnings: list[str] = []
    beats_out: list[RenderBeat] = []
    ordered = sorted(sentence_ledger.sentences, key=lambda row: row.speech_start_sec)
    prev_pair: tuple[str, str] | None = None

    speech_duration = lambda se: max(1e-9, se.speech_end_sec - se.speech_start_sec)

    for si, sentence in enumerate(ordered):
        sid = sentence.sentence_id
        shots_assignment = assignment_by_sentence[sid]

        beat_expected = sentence.beat_count

        sd = speech_duration(sentence)
        ceil_sd = math.ceil(sd - 1e-12)
        if ceil_sd != sentence.beat_count:
            warnings.append(
                f"sentence {sid}: ledger beat_count {sentence.beat_count} != ceil(duration) {ceil_sd}"
            )

        s_speech = sentence.speech_start_sec
        e_speech = sentence.speech_end_sec

        next_speech_start: float | None = None
        if si + 1 < len(ordered):
            next_speech_start = ordered[si + 1].speech_start_sec

        for j in range(beat_expected):
            shot_ref = shots_assignment[j]
            clip_obj, identified = moments[shot_ref.clip_id, shot_ref.moment_id]

            last_beat_in_sentence = j == beat_expected - 1

            if not last_beat_in_sentence:
                timeline_start = s_speech + float(j)
                timeline_end = timeline_start + 1.0
            else:
                timeline_start = s_speech + float(beat_expected - 1)
                end_speech_floor = max(e_speech, timeline_start + 1e-6)
                if next_speech_start is not None:
                    timeline_end = max(end_speech_floor, float(next_speech_start))
                else:
                    timeline_end = max(end_speech_floor, audio_duration_sec)

            timeline_duration = timeline_end - timeline_start
            if timeline_duration <= 0:
                raise ValueError(f"non-positive timeline for {sid} beat {j}")

            source_start, source_end = resolve_source_window(
                identified.key_instant_sec,
                identified,
                clip_obj,
                timeline_duration,
            )
            source_duration = source_end - source_start
            shot_span = identified.end_sec - identified.start_sec
            if source_duration + 1e-5 < timeline_duration:
                warnings.append(
                    f"beat {sid}-{j}: usable source {source_duration:.3f}s < timeline "
                    f"{timeline_duration:.3f}s (shot span {shot_span:.3f}s; "
                    f"playbackRate {source_duration / timeline_duration:.3f})"
                )

            playback_rate = source_duration / timeline_duration

            pair = (shot_ref.clip_id, shot_ref.moment_id)
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
                    clipId=shot_ref.clip_id,
                    momentId=identified.moment_id,
                    sourcePath=clip_obj.source_path,
                    sourceStartSec=source_start,
                    sourceEndSec=source_end,
                    timelineStartSec=timeline_start,
                    timelineEndSec=timeline_end,
                    playbackRate=playback_rate,
                )
            )

    words_render = [
        RenderWord(word=w.word, startSec=w.start_sec, endSec=w.end_sec) for w in whisper_words
    ]
    hook = hook_text.strip() if hook_text else (ordered[0].text.strip() if ordered else "Short")

    duration_sec = max(
        audio_duration_sec, max((b.timeline_end_sec for b in beats_out), default=0.0)
    )

    return RenderPlan(
        runId=run_id,
        createdAt=created_at,
        durationSec=duration_sec,
        voiceoverStaticPath=voiceover_static_path,
        theme=RenderTheme(hookText=hook),
        beats=sorted(beats_out, key=lambda b: (b.timeline_start_sec, b.beat_id)),
        words=words_render,
        warnings=warnings,
    )
