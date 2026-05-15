"""Validate Shot match against Analysis and the sentence ledger → resolved editorial rows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from contracts import SentenceEntry, SentenceLedger
from edit.schema_shot_match import ShotMatch, ShotRef
from vlm.schema import Clip, IdentifiedShot, VlmAnalysis

EPSILON = 1e-6


@dataclass(frozen=True)
class ResolvedShot:
    clip_ref: str
    shot_ref: str
    beat_span: int
    clip: Clip
    shot: IdentifiedShot


@dataclass(frozen=True)
class ResolvedSentence:
    sentence: SentenceEntry
    shots: list[ResolvedShot]


def _shot_map(analysis: VlmAnalysis) -> dict[tuple[str, str], tuple[Clip, IdentifiedShot]]:
    mapping: dict[tuple[str, str], tuple[Clip, IdentifiedShot]] = {}
    for clip in analysis.clips:
        for shot in clip.identified_shots:
            mapping[(clip.id, shot.shot_id)] = (clip, shot)
    return mapping


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
    """Return ordered, validated resolved sentence rows used by render-plan assembly."""
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
    for sentence_index, sentence in enumerate(ordered):
        sid = sentence.sentence_id
        shots_assignment = assignment_by_sentence.get(sid)
        if shots_assignment is None:
            raise ValueError(f"missing assignments for sentence {sid!r}")
        beat_expected = sentence.beat_count
        if sentence_index == 0 and any(shot_ref.beat_span != 1 for shot_ref in shots_assignment):
            raise ValueError(f"sentence {sid!r}: hook shots must have beatSpan=1")
        beat_total = sum(shot_ref.beat_span for shot_ref in shots_assignment)
        if beat_total != beat_expected:
            raise ValueError(
                f"sentence {sid!r}: expected {beat_expected} total beats, got {beat_total}"
            )
        seen_refs: set[tuple[str, str]] = set()
        for shot_ref in shots_assignment:
            ref = (shot_ref.clip_id, shot_ref.shot_id)
            if ref in seen_refs:
                raise ValueError(
                    f"sentence {sid!r}: duplicate shot ref {ref!r}; "
                    "use a higher beatSpan on one entry instead"
                )
            seen_refs.add(ref)
            if shot_ref.beat_span > beat_expected:
                raise ValueError(
                    f"sentence {sid!r}: beatSpan {shot_ref.beat_span} exceeds "
                    f"beatCount {beat_expected}"
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
                    beat_span=shot_ref.beat_span,
                    clip=clip_obj,
                    shot=identified_shot,
                )
            )
        resolved.append(ResolvedSentence(sentence=sentence, shots=resolved_shots))
    return resolved
