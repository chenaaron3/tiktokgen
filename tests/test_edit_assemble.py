import pytest

from contracts import SentenceEntry, SentenceLedger, WordToken
from edit.assemble import assemble_render_plan, build_resolved_sentences
from edit.schema_shot_match import SentenceAssignment, ShotMatch, ShotRef
from edit.vlm_shots import build_vlm_shots_for_prompt
from vlm.schema import Clip, IdentifiedShot, Provider, TwelveLabsClipRef, VlmAnalysis


def _analysis() -> VlmAnalysis:
    shot = IdentifiedShot(
        shotId="m1",
        startSec=0.0,
        endSec=4.0,
        vlmTag="utensil_lift",
        confidenceScore=0.9,
        keyInstantSec=2.0,
        reasoning="lift",
    )
    clip = Clip(
        id="c0",
        sourcePath="/tmp/x.mov",
        originalFilename="x.mov",
        durationSec=20.0,
        capturedAt=None,
        location=None,
        media={},
        twelveLabs=TwelveLabsClipRef(assetId="a", taskId="t"),
        summary="s",
        identifiedShots=[shot],
    )
    return VlmAnalysis(
        runId="r",
        analyzedAt="t",
        provider=Provider(name="p", model="m", rawResponseRef=""),
        clips=[clip],
    )


def test_vlm_shots_row_shape_has_no_paths():
    rows = build_vlm_shots_for_prompt(_analysis())
    assert rows and set(rows[0].keys()) <= {
        "clipId",
        "shotId",
        "vlmTag",
        "confidenceScore",
        "reasoning",
    }


def test_assemble_requires_matching_shot_count():
    analysis = _analysis()
    ledger = SentenceLedger(
        sentences=[
            SentenceEntry(
                sentenceId="s0",
                text="Hi.",
                speechStartSec=0.0,
                speechEndSec=0.8,
                beatCount=1,
            )
        ]
    )
    bad = ShotMatch(
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                text="Hi.",
                shots=[],
            ),
        ],
    )
    with pytest.raises(ValueError, match="expected 1 shots"):
        build_resolved_sentences(
            shot_match=bad,
            analysis=analysis,
            sentence_ledger=ledger,
            audio_duration_sec=0.8,
        )


def test_happy_assemble_matches_fixture_pipeline():
    analysis = _analysis()
    second_shot = IdentifiedShot(
        shotId="m2",
        startSec=4.0,
        endSec=7.5,
        vlmTag="texture_macro",
        confidenceScore=0.85,
        keyInstantSec=4.25,
        reasoning="stretch",
    )
    third_shot = IdentifiedShot(
        shotId="m3",
        startSec=7.5,
        endSec=9.5,
        vlmTag="texture_macro",
        confidenceScore=0.82,
        keyInstantSec=8.0,
        reasoning="close-up",
    )
    analysis.clips[0].identified_shots.extend([second_shot, third_shot])

    ledger = SentenceLedger(
        sentences=[
            SentenceEntry(
                sentenceId="s0",
                text="Hello.",
                speechStartSec=0.0,
                speechEndSec=1.0,
                beatCount=1,
            ),
            SentenceEntry(
                sentenceId="s1",
                text="Again now.",
                speechStartSec=1.0,
                speechEndSec=3.0,
                beatCount=2,
            ),
        ]
    )

    shot_match = ShotMatch(
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                text="Hello.",
                shots=[ShotRef(clipId="c0", shotId="m1")],
            ),
            SentenceAssignment(
                sentenceId="s1",
                text="Again now.",
                shots=[ShotRef(clipId="c0", shotId="m2"), ShotRef(clipId="c0", shotId="m3")],
            ),
        ],
    )
    resolved = build_resolved_sentences(
        shot_match=shot_match,
        analysis=analysis,
        sentence_ledger=ledger,
        audio_duration_sec=3.0,
    )

    plan = assemble_render_plan(
        resolved_sentences=resolved,
        whisper_words=[
            WordToken(word="hello", startSec=0.0, endSec=1.0),
            WordToken(word="again", startSec=1.0, endSec=2.0),
            WordToken(word="now", startSec=2.0, endSec=3.0),
        ],
        voiceover_static_path="/tmp/audio.mp3",
        audio_duration_sec=3.0,
        run_id="runit",
        created_at="iso",
        hook_text="Hi",
    )
    assert len(plan.beats) == 3
    beats = sorted(plan.beats, key=lambda b: b.timeline_start_sec)
    assert abs(beats[0].timeline_start_sec - 0.0) < 1e-9
    assert abs(beats[0].timeline_end_sec - 1.0) < 1e-9
    assert abs(beats[1].timeline_start_sec - 1.0) < 1e-9
    assert abs(beats[1].timeline_end_sec - 2.0) < 1e-9
    assert abs(beats[2].timeline_start_sec - 2.0) < 1e-9
    assert abs(beats[2].timeline_end_sec - 3.0) < 1e-9
    assert all(abs(b.playback_rate - 1.0) < 1e-9 for b in beats)
    assert abs(plan.duration_sec - 3.0) < 1e-9
    dumped = plan.model_dump(by_alias=True)
    assert "beats" in dumped
    assert dumped["beats"][0]["shotId"] == "m1"


def test_assemble_rejects_nonzero_first_sentence_start():
    analysis = _analysis()
    ledger = SentenceLedger(
        sentences=[
            SentenceEntry(
                sentenceId="s0",
                text="Hi.",
                speechStartSec=0.1,
                speechEndSec=1.0,
                beatCount=1,
            )
        ]
    )
    match = ShotMatch(
        assignments=[SentenceAssignment(sentenceId="s0", text="Hi.", shots=[ShotRef(clipId="c0", shotId="m1")])]
    )
    with pytest.raises(ValueError, match="first sentence must start at 0"):
        build_resolved_sentences(
            shot_match=match,
            analysis=analysis,
            sentence_ledger=ledger,
            audio_duration_sec=1.0,
        )


def test_assemble_rejects_sentence_gap():
    analysis = _analysis()
    second_shot = IdentifiedShot(
        shotId="m2",
        startSec=4.0,
        endSec=8.0,
        vlmTag="texture_macro",
        confidenceScore=0.8,
        keyInstantSec=4.5,
        reasoning="alt",
    )
    analysis.clips[0].identified_shots.append(second_shot)
    ledger = SentenceLedger(
        sentences=[
            SentenceEntry(
                sentenceId="s0",
                text="One.",
                speechStartSec=0.0,
                speechEndSec=1.0,
                beatCount=1,
            ),
            SentenceEntry(
                sentenceId="s1",
                text="Two.",
                speechStartSec=1.2,
                speechEndSec=2.0,
                beatCount=1,
            ),
        ]
    )
    match = ShotMatch(
        assignments=[
            SentenceAssignment(sentenceId="s0", text="One.", shots=[ShotRef(clipId="c0", shotId="m1")]),
            SentenceAssignment(sentenceId="s1", text="Two.", shots=[ShotRef(clipId="c0", shotId="m2")]),
        ]
    )
    with pytest.raises(ValueError, match="sentence ledger must be contiguous"):
        build_resolved_sentences(
            shot_match=match,
            analysis=analysis,
            sentence_ledger=ledger,
            audio_duration_sec=2.0,
        )


def test_assemble_requires_last_sentence_end_to_match_audio():
    analysis = _analysis()
    ledger = SentenceLedger(
        sentences=[
            SentenceEntry(
                sentenceId="s0",
                text="Hi.",
                speechStartSec=0.0,
                speechEndSec=0.8,
                beatCount=1,
            )
        ]
    )
    match = ShotMatch(
        assignments=[SentenceAssignment(sentenceId="s0", text="Hi.", shots=[ShotRef(clipId="c0", shotId="m1")])]
    )
    with pytest.raises(ValueError, match="last sentence must end at audio duration"):
        build_resolved_sentences(
            shot_match=match,
            analysis=analysis,
            sentence_ledger=ledger,
            audio_duration_sec=1.0,
        )


def test_source_window_shifts_left_when_key_near_right_edge():
    shot = IdentifiedShot(
        shotId="m1",
        startSec=5.0,
        endSec=7.0,
        vlmTag="utensil_lift",
        confidenceScore=0.9,
        keyInstantSec=6.8,
        reasoning="lift",
    )
    clip = Clip(
        id="c0",
        sourcePath="/tmp/x.mov",
        originalFilename="x.mov",
        durationSec=7.0,
        capturedAt=None,
        location=None,
        media={},
        twelveLabs=TwelveLabsClipRef(assetId="a", taskId="t"),
        summary="s",
        identifiedShots=[shot],
    )
    analysis = VlmAnalysis(
        runId="r",
        analyzedAt="t",
        provider=Provider(name="p", model="m", rawResponseRef=""),
        clips=[clip],
    )
    ledger = SentenceLedger(
        sentences=[
            SentenceEntry(
                sentenceId="s0",
                text="Stretch.",
                speechStartSec=0.0,
                speechEndSec=1.5,
                beatCount=1,
            )
        ]
    )
    match = ShotMatch(
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                text="Stretch.",
                shots=[ShotRef(clipId="c0", shotId="m1")],
            )
        ]
    )
    resolved = build_resolved_sentences(
        shot_match=match,
        analysis=analysis,
        sentence_ledger=ledger,
        audio_duration_sec=1.5,
    )
    plan = assemble_render_plan(
        resolved_sentences=resolved,
        whisper_words=[],
        voiceover_static_path="static:x",
        audio_duration_sec=1.5,
        run_id="r",
        created_at="t",
    )
    beat = plan.beats[0]
    assert abs(beat.source_start_sec - 5.5) < 1e-9
    assert abs(beat.source_end_sec - 7.0) < 1e-9
    assert abs((beat.source_end_sec - beat.source_start_sec) - 1.5) < 1e-9
