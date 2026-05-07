from edit.assemble import assemble_render_plan
from edit.schema_shot_match import SentenceAssignment, ShotMatch, ShotRef, ShotSentenceLine
from edit.vlm_shots import build_vlm_shots_for_prompt
from vlm.schema import Clip, IdentifiedShot, Provider, TwelveLabsClipRef, VlmAnalysis


def _analysis() -> VlmAnalysis:
    shot = IdentifiedShot(
        momentId="m1",
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
        schemaVersion="0.4.1",
        runId="r",
        analyzedAt="t",
        provider=Provider(name="p", model="m", rawResponseRef=""),
        clips=[clip],
    )


def test_vlm_shots_row_shape_has_no_paths():
    rows = build_vlm_shots_for_prompt(_analysis())
    assert rows and set(rows[0].keys()) <= {
        "clipId",
        "momentId",
        "vlmTag",
        "confidenceScore",
        "reasoning",
    }


def test_assemble_requires_matching_shot_count():
    from contracts import SentenceEntry, SentenceLedger

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
        schemaVersion="0.2.0",
        sentences=[ShotSentenceLine(sentenceId="s0", text="Hi.")],
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                shots=[],
            )
        ],
    )
    try:
        assemble_render_plan(
            shot_match=bad,
            analysis=analysis,
            sentence_ledger=ledger,
            whisper_words=[],
            voiceover_static_path="static:x",
            audio_duration_sec=5.0,
            run_id="r",
            created_at="t",
        )
        raise AssertionError("expected failure")
    except ValueError as error:
        assert "expected 1 shots" in str(error)


def test_happy_assemble_matches_fixture_pipeline():
    from contracts import SentenceEntry, SentenceLedger, WordToken

    analysis = _analysis()
    second_shot = IdentifiedShot(
        momentId="m2",
        startSec=5.0,
        endSec=7.5,
        vlmTag="texture_macro",
        confidenceScore=0.85,
        keyInstantSec=6.25,
        reasoning="stretch",
    )
    analysis.clips[0].identified_shots.append(second_shot)

    ledger = SentenceLedger(
        sentences=[
            SentenceEntry(
                sentenceId="s0",
                text="Hello.",
                speechStartSec=0.0,
                speechEndSec=0.9,
                beatCount=1,
            ),
            SentenceEntry(
                sentenceId="s1",
                text="Again.",
                speechStartSec=1.5,
                speechEndSec=2.4,
                beatCount=1,
            ),
        ]
    )

    shot_match = ShotMatch(
        schemaVersion="0.2.0",
        sentences=[
            ShotSentenceLine(sentenceId="s0", text="Hello."),
            ShotSentenceLine(sentenceId="s1", text="Again."),
        ],
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                shots=[ShotRef(clipId="c0", momentId="m1")],
            ),
            SentenceAssignment(
                sentenceId="s1",
                shots=[ShotRef(clipId="c0", momentId="m2")],
            ),
        ],
    )

    plan = assemble_render_plan(
        shot_match=shot_match,
        analysis=analysis,
        sentence_ledger=ledger,
        whisper_words=[
            WordToken(word="hello", startSec=0.0, endSec=0.9),
            WordToken(word="again", startSec=1.5, endSec=2.4),
        ],
        voiceover_static_path="/tmp/audio.mp3",
        audio_duration_sec=3.0,
        run_id="runit",
        created_at="iso",
        hook_text="Hi",
    )
    assert len(plan.beats) == 2
    first = min(plan.beats, key=lambda b: b.timeline_start_sec)
    assert abs(first.timeline_end_sec - 1.5) < 1e-9
    src_dur = first.source_end_sec - first.source_start_sec
    t_dur = first.timeline_end_sec - first.timeline_start_sec
    assert abs(src_dur - t_dur) < 1e-5
    assert abs(first.playback_rate - 1.0) < 1e-5
    dumped = plan.model_dump(by_alias=True)
    assert "beats" in dumped
