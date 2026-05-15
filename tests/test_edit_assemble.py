import pytest

from contracts import SentenceEntry, SentenceLedger, WordToken
from edit.assemble import assemble_render_plan, build_resolved_sentences
from edit.schema_shot_match import SentenceAssignment, ShotMatch, ShotRef
from vlm.schema import Clip, ClipMedia, IdentifiedShot, Provider, TwelveLabsClipRef, VlmAnalysis


def _analysis() -> VlmAnalysis:
    shot = IdentifiedShot(
        shotId="m1",
        startSec=0.0,
        endSec=4.0,
        vlmTag="the_interaction",
        keyInstantStartSec=2.0,
        reasoning="lift",
        labelConfidence="high",
        verifiedBy="twelvelabs",
    )
    clip = Clip(
        id="c0",
        sourcePath="/tmp/x.mov",
        originalFilename="x.mov",
        durationSec=20.0,
        capturedAt=None,
        location=None,
        media=ClipMedia.empty(),
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
        _planning="Test planning for mismatched shot count.",
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                text="Hi.",
                shots=[],
            ),
        ],
    )
    with pytest.raises(ValueError, match="expected 1 total beats, got 0"):
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
        keyInstantStartSec=4.25,
        reasoning="stretch",
        labelConfidence="high",
        verifiedBy="twelvelabs",
    )
    third_shot = IdentifiedShot(
        shotId="m3",
        startSec=7.5,
        endSec=9.5,
        vlmTag="texture_macro",
        keyInstantStartSec=8.0,
        reasoning="close-up",
        labelConfidence="high",
        verifiedBy="twelvelabs",
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
        _planning="Test planning for happy path assembly.",
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                text="Hello.",
                shots=[
                    ShotRef(
                        clipId="c0",
                        shotId="m1",
                        beatSpan=1,
                        reasoning="Opens on the first beat.",
                    )
                ],
            ),
            SentenceAssignment(
                sentenceId="s1",
                text="Again now.",
                shots=[
                    ShotRef(
                        clipId="c0",
                        shotId="m2",
                        beatSpan=1,
                        reasoning="Introduces the next visual beat.",
                    ),
                    ShotRef(
                        clipId="c0",
                        shotId="m3",
                        beatSpan=1,
                        reasoning="Provides variation for the second beat.",
                    ),
                ],
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
        overlay_text="Hi",
    )
    assert len(plan.beats) == 3
    beats = sorted(plan.beats, key=lambda b: b.timeline_start_sec)
    assert abs(beats[0].timeline_start_sec - 0.0) < 1e-9
    assert abs(beats[0].timeline_end_sec - 1.0) < 1e-9
    assert abs(beats[1].timeline_start_sec - 1.0) < 1e-9
    assert abs(beats[1].timeline_end_sec - 2.0) < 1e-9
    assert abs(beats[2].timeline_start_sec - 2.0) < 1e-9
    assert abs(beats[2].timeline_end_sec - 3.0) < 1e-9
    assert abs(plan.duration_sec - 3.0) < 1e-9
    dumped = plan.model_dump(by_alias=True)
    assert "beats" in dumped
    assert dumped["beats"][0]["shotId"] == "m1"
    assert "playbackRate" not in dumped["beats"][0]


def test_assemble_allows_two_beat_span_for_body_shot():
    analysis = _analysis()
    second_shot = IdentifiedShot(
        shotId="m2",
        startSec=4.0,
        endSec=8.0,
        vlmTag="texture_macro",
        keyInstantStartSec=4.25,
        reasoning="stretch",
        labelConfidence="high",
        verifiedBy="twelvelabs",
    )
    analysis.clips[0].identified_shots.append(second_shot)
    ledger = SentenceLedger(
        sentences=[
            SentenceEntry(
                sentenceId="s0",
                text="Hook.",
                speechStartSec=0.0,
                speechEndSec=1.0,
                beatCount=1,
            ),
            SentenceEntry(
                sentenceId="s1",
                text="Body line.",
                speechStartSec=1.0,
                speechEndSec=3.0,
                beatCount=2,
            ),
        ]
    )
    shot_match = ShotMatch(
        _planning="Test planning for body two-beat hold.",
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                text="Hook.",
                shots=[
                    ShotRef(
                        clipId="c0",
                        shotId="m1",
                        beatSpan=1,
                        reasoning="Uses a single-beat hook shot.",
                    )
                ],
            ),
            SentenceAssignment(
                sentenceId="s1",
                text="Body line.",
                shots=[
                    ShotRef(
                        clipId="c0",
                        shotId="m2",
                        beatSpan=2,
                        reasoning="Holds a strong texture shot for two beats.",
                    )
                ],
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
        whisper_words=[],
        voiceover_static_path="/tmp/audio.mp3",
        audio_duration_sec=3.0,
        run_id="runit",
        created_at="iso",
    )
    assert len(plan.beats) == 2
    beats = sorted(plan.beats, key=lambda b: b.timeline_start_sec)
    assert abs(beats[0].timeline_end_sec - 1.0) < 1e-9
    assert abs(beats[1].timeline_start_sec - 1.0) < 1e-9
    assert abs(beats[1].timeline_end_sec - 3.0) < 1e-9


def test_assemble_allows_multi_beat_hold_on_one_shot_ref():
    analysis = _analysis()
    ledger = SentenceLedger(
        sentences=[
            SentenceEntry(
                sentenceId="s0",
                text="Hook.",
                speechStartSec=0.0,
                speechEndSec=1.0,
                beatCount=1,
            ),
            SentenceEntry(
                sentenceId="s1",
                text="The burger was juicy, flavorful, and satisfying.",
                speechStartSec=1.0,
                speechEndSec=7.0,
                beatCount=3,
            ),
        ]
    )
    shot_match = ShotMatch(
        _planning="Test planning for three-beat hold on one shot.",
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                text="Hook.",
                shots=[
                    ShotRef(
                        clipId="c0",
                        shotId="m1",
                        beatSpan=1,
                        reasoning="Uses a single-beat hook shot.",
                    )
                ],
            ),
            SentenceAssignment(
                sentenceId="s1",
                text="The burger was juicy, flavorful, and satisfying.",
                shots=[
                    ShotRef(
                        clipId="c0",
                        shotId="m1",
                        beatSpan=3,
                        reasoning="One macro hold covers the full burger praise line.",
                    )
                ],
            ),
        ],
    )
    resolved = build_resolved_sentences(
        shot_match=shot_match,
        analysis=analysis,
        sentence_ledger=ledger,
        audio_duration_sec=7.0,
    )
    plan = assemble_render_plan(
        resolved_sentences=resolved,
        whisper_words=[],
        voiceover_static_path="/tmp/audio.mp3",
        audio_duration_sec=7.0,
        run_id="runit",
        created_at="iso",
    )
    assert len(plan.beats) == 2
    body = [b for b in plan.beats if b.sentence_id == "s1"][0]
    assert abs(body.timeline_end_sec - body.timeline_start_sec - 6.0) < 1e-9


def test_resolve_rejects_duplicate_shot_ref_in_sentence():
    analysis = _analysis()
    ledger = SentenceLedger(
        sentences=[
            SentenceEntry(
                sentenceId="s0",
                text="Hook.",
                speechStartSec=0.0,
                speechEndSec=1.0,
                beatCount=1,
            ),
            SentenceEntry(
                sentenceId="s1",
                text="Body line.",
                speechStartSec=1.0,
                speechEndSec=7.0,
                beatCount=3,
            ),
        ]
    )
    shot_match = ShotMatch(
        _planning="Test planning with duplicate shot refs.",
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                text="Hook.",
                shots=[
                    ShotRef(
                        clipId="c0",
                        shotId="m1",
                        beatSpan=1,
                        reasoning="Hook shot.",
                    )
                ],
            ),
            SentenceAssignment(
                sentenceId="s1",
                text="Body line.",
                shots=[
                    ShotRef(
                        clipId="c0",
                        shotId="m1",
                        beatSpan=1,
                        reasoning="First beat.",
                    ),
                    ShotRef(
                        clipId="c0",
                        shotId="m1",
                        beatSpan=1,
                        reasoning="Second beat.",
                    ),
                    ShotRef(
                        clipId="c0",
                        shotId="m1",
                        beatSpan=1,
                        reasoning="Third beat.",
                    ),
                ],
            ),
        ],
    )
    with pytest.raises(ValueError, match="duplicate shot ref"):
        build_resolved_sentences(
            shot_match=shot_match,
            analysis=analysis,
            sentence_ledger=ledger,
            audio_duration_sec=7.0,
        )


def test_assemble_rejects_hook_shot_with_two_beat_span():
    analysis = _analysis()
    ledger = SentenceLedger(
        sentences=[
            SentenceEntry(
                sentenceId="s0",
                text="Hook.",
                speechStartSec=0.0,
                speechEndSec=1.0,
                beatCount=1,
            )
        ]
    )
    match = ShotMatch(
        _planning="Test planning for hook beatSpan validation.",
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                text="Hook.",
                shots=[
                    ShotRef(
                        clipId="c0",
                        shotId="m1",
                        beatSpan=2,
                        reasoning="Invalid two-beat hook shot.",
                    )
                ],
            )
        ],
    )
    with pytest.raises(ValueError, match="hook shots must have beatSpan=1"):
        build_resolved_sentences(
            shot_match=match,
            analysis=analysis,
            sentence_ledger=ledger,
            audio_duration_sec=1.0,
        )


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
        _planning="Test planning for first sentence start validation.",
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                text="Hi.",
                shots=[
                    ShotRef(
                        clipId="c0",
                        shotId="m1",
                        beatSpan=1,
                        reasoning="Covers the only beat.",
                    )
                ],
            )
        ]
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
        keyInstantStartSec=4.5,
        reasoning="alt",
        labelConfidence="high",
        verifiedBy="twelvelabs",
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
        _planning="Test planning for sentence gap validation.",
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                text="One.",
                shots=[
                    ShotRef(
                        clipId="c0",
                        shotId="m1",
                        beatSpan=1,
                        reasoning="Represents the first sentence.",
                    )
                ],
            ),
            SentenceAssignment(
                sentenceId="s1",
                text="Two.",
                shots=[
                    ShotRef(
                        clipId="c0",
                        shotId="m2",
                        beatSpan=1,
                        reasoning="Represents the second sentence.",
                    )
                ],
            ),
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
        _planning="Test planning for last sentence end validation.",
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                text="Hi.",
                shots=[
                    ShotRef(
                        clipId="c0",
                        shotId="m1",
                        beatSpan=1,
                        reasoning="Matches the short greeting.",
                    )
                ],
            )
        ]
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
        vlmTag="the_interaction",
        keyInstantStartSec=6.8,
        reasoning="lift",
        labelConfidence="high",
        verifiedBy="twelvelabs",
    )
    clip = Clip(
        id="c0",
        sourcePath="/tmp/x.mov",
        originalFilename="x.mov",
        durationSec=7.0,
        capturedAt=None,
        location=None,
        media=ClipMedia.empty(),
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
        _planning="Test planning for source window edge handling.",
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                text="Stretch.",
                shots=[
                    ShotRef(
                        clipId="c0",
                        shotId="m1",
                        beatSpan=1,
                        reasoning="Keeps focus on the key instant.",
                    )
                ],
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
        voiceover_static_path="/tmp/voice.mp3",
        audio_duration_sec=1.5,
        run_id="r",
        created_at="t",
    )
    beat = plan.beats[0]
    assert abs(beat.source_start_sec - 5.5) < 1e-9
    assert abs(beat.source_end_sec - 7.0) < 1e-9
    assert abs((beat.source_end_sec - beat.source_start_sec) - 1.5) < 1e-9


def test_source_window_uses_full_clip_duration_when_shot_window_too_short():
    shot = IdentifiedShot(
        shotId="m1",
        startSec=1.1,
        endSec=2.0,
        vlmTag="the_interaction",
        keyInstantStartSec=1.2,
        reasoning="lift",
        labelConfidence="high",
        verifiedBy="twelvelabs",
    )
    clip = Clip(
        id="c0",
        sourcePath="/tmp/x.mov",
        originalFilename="x.mov",
        durationSec=3.0,
        capturedAt=None,
        location=None,
        media=ClipMedia.empty(),
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
                text="Stretch longer.",
                speechStartSec=0.0,
                speechEndSec=2.5,
                beatCount=1,
            )
        ]
    )
    match = ShotMatch(
        _planning="Test planning for clip-duration bounded source windows.",
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                text="Stretch longer.",
                shots=[
                    ShotRef(
                        clipId="c0",
                        shotId="m1",
                        beatSpan=1,
                        reasoning="Uses available clip duration.",
                    )
                ],
            )
        ],
    )
    resolved = build_resolved_sentences(
        shot_match=match,
        analysis=analysis,
        sentence_ledger=ledger,
        audio_duration_sec=2.5,
    )
    plan = assemble_render_plan(
        resolved_sentences=resolved,
        whisper_words=[],
        voiceover_static_path="/tmp/voice.mp3",
        audio_duration_sec=2.5,
        run_id="r",
        created_at="t",
    )
    beat = plan.beats[0]
    assert beat.source_start_sec >= 0.0
    assert beat.source_end_sec <= 3.0
    assert abs((beat.source_end_sec - beat.source_start_sec) - 2.5) < 1e-9


def test_short_clip_is_retimed_instead_of_raising():
    shot = IdentifiedShot(
        shotId="m1",
        startSec=1.1,
        endSec=2.0,
        vlmTag="the_interaction",
        keyInstantStartSec=1.2,
        reasoning="lift",
        labelConfidence="high",
        verifiedBy="twelvelabs",
    )
    clip = Clip(
        id="c0",
        sourcePath="/tmp/x.mov",
        originalFilename="x.mov",
        durationSec=1.898,
        capturedAt=None,
        location=None,
        media=ClipMedia.empty(),
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
                text="Short clip retime.",
                speechStartSec=0.0,
                speechEndSec=1.975,
                beatCount=1,
            )
        ]
    )
    match = ShotMatch(
        _planning="Test planning for short clip retiming.",
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                text="Short clip retime.",
                shots=[
                    ShotRef(
                        clipId="c0",
                        shotId="m1",
                        beatSpan=1,
                        reasoning="Uses retime fallback.",
                    )
                ],
            )
        ],
    )
    resolved = build_resolved_sentences(
        shot_match=match,
        analysis=analysis,
        sentence_ledger=ledger,
        audio_duration_sec=1.975,
    )
    plan = assemble_render_plan(
        resolved_sentences=resolved,
        whisper_words=[],
        voiceover_static_path="/tmp/voice.mp3",
        audio_duration_sec=1.975,
        run_id="r",
        created_at="t",
    )
    beat = plan.beats[0]
    assert abs(beat.source_start_sec - 0.0) < 1e-9
    assert abs(beat.source_end_sec - 1.898) < 1e-9
    assert plan.warnings and "short source window retimed" in plan.warnings[0]
    assert "rate=0." in plan.warnings[0]


def test_assemble_uses_explicit_empty_hook_without_fallback():
    analysis = _analysis()
    ledger = SentenceLedger(
        sentences=[
            SentenceEntry(
                sentenceId="s0",
                text="Hook sentence fallback.",
                speechStartSec=0.0,
                speechEndSec=1.0,
                beatCount=1,
            )
        ]
    )
    shot_match = ShotMatch(
        _planning="Test planning for explicit empty hook behavior.",
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                text="Hook sentence fallback.",
                shots=[
                    ShotRef(
                        clipId="c0",
                        shotId="m1",
                        beatSpan=1,
                        reasoning="Uses the only available shot.",
                    )
                ],
            )
        ],
    )
    resolved = build_resolved_sentences(
        shot_match=shot_match,
        analysis=analysis,
        sentence_ledger=ledger,
        audio_duration_sec=1.0,
    )
    plan = assemble_render_plan(
        resolved_sentences=resolved,
        whisper_words=[],
        voiceover_static_path="/tmp/audio.mp3",
        audio_duration_sec=1.0,
        run_id="runit",
        created_at="iso",
        overlay_text="",
    )
    assert plan.theme is not None
    assert plan.theme.overlay_text == ""
