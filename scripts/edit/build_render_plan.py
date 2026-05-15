"""Resolved editorial rows → Render plan timeline (deterministic; no LLM)."""

from __future__ import annotations

import json
from collections.abc import Sequence

from contracts import WordToken
from edit.resolve_shot_match import EPSILON, ResolvedSentence
from edit.schema_render_plan import RenderBeat, RenderPlan, RenderTheme, RenderWord
from util.path_util import PathUtil
from vlm.schema import Clip, IdentifiedShot


def resolve_source_window(
    key_instant_start_sec: float,
    shot: IdentifiedShot,
    clip: Clip,
    timeline_duration_sec: float,
) -> tuple[float, float, float]:
    """Build a fixed-duration source window anchored at ``key_instant_start_sec``.

    If requested duration exceeds available clip duration, use the maximum in-clip window
    and return a playback_rate that callers can use to fill the target timeline duration.
    """
    shot_start = shot.start_sec
    shot_end = shot.end_sec
    if shot_end < shot_start:
        raise ValueError("shot endSec < startSec")
    td = float(timeline_duration_sec)
    if td <= 0:
        raise ValueError("timeline_duration_sec must be positive")
    clip_lo = 0.0
    clip_hi = float(clip.duration_sec) if clip.duration_sec is not None else float("inf")
    if clip_hi <= clip_lo:
        raise ValueError(f"cannot form window for clip {clip.id} shot {shot.shot_id}")
    max_duration = clip_hi - clip_lo
    if td > max_duration + EPSILON:
        td = max_duration

    s = key_instant_start_sec
    e = key_instant_start_sec + td

    if e > clip_hi:
        shift = e - clip_hi
        s -= shift
        e -= shift
    if s < clip_lo:
        shift = clip_lo - s
        s += shift
        e += shift

    if s < clip_lo - EPSILON or e > clip_hi + EPSILON:
        raise ValueError(f"cannot fit source window for clip {clip.id} shot {shot.shot_id}")
    source_duration = e - s
    if source_duration <= 0:
        raise ValueError(f"cannot form positive window for clip {clip.id} shot {shot.shot_id}")
    playback_rate = source_duration / timeline_duration_sec
    return s, e, playback_rate


def assemble_render_plan(
    resolved_sentences: Sequence[ResolvedSentence],
    whisper_words: Sequence[WordToken],
    voiceover_static_path: str,
    audio_duration_sec: float,
    run_id: str,
    created_at: str,
    overlay_text: str | None = None,
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
        seconds_per_beat = sentence_duration / float(beat_expected)
        if seconds_per_beat <= 0:
            raise ValueError(f"non-positive allocated shot duration for {sid}")

        for j, resolved_shot in enumerate(resolved_sentence.shots):
            timeline_start = timeline_cursor
            shot_timeline_duration = seconds_per_beat * float(resolved_shot.beat_span)
            timeline_end = timeline_start + shot_timeline_duration
            timeline_cursor = timeline_end
            source_start, source_end, playback_rate = resolve_source_window(
                resolved_shot.shot.key_instant_start_sec,
                resolved_shot.shot,
                resolved_shot.clip,
                shot_timeline_duration,
            )
            source_duration = source_end - source_start
            if source_duration <= 0:
                raise ValueError(
                    f"cannot form positive source duration for clip {resolved_shot.clip_ref} "
                    f"shot {resolved_shot.shot_ref}"
                )
            if playback_rate + EPSILON < 1.0:
                warnings.append(
                    "short source window retimed to fill beat duration: "
                    f"clip={resolved_shot.clip_ref} shot={resolved_shot.shot_ref} "
                    f"source={source_duration:.3f}s timeline={shot_timeline_duration:.3f}s "
                    f"rate={playback_rate:.3f}"
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
                )
            )

    words_render = [
        RenderWord(word=w.word, startSec=w.start_sec, endSec=w.end_sec) for w in whisper_words
    ]
    overlay = (
        overlay_text.strip()
        if overlay_text is not None
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
        theme=RenderTheme(overlayText=overlay),
        beats=sorted(beats_out, key=lambda b: (b.timeline_start_sec, b.beat_id)),
        words=words_render,
        warnings=warnings,
    )
    if paths is not None:
        plan_path = paths.render_plan_json()
        plan_path.write_text(
            json.dumps(plan.model_dump(by_alias=True), indent=2, ensure_ascii=False) + "\n"
        )
        print(f"Wrote render plan: {plan_path}")
    return plan
