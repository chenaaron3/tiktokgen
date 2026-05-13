"""Shot-match orchestrator stub (no LiteLLM)."""

from contracts import SentenceEntry, SentenceLedger
from edit.schema_shot_match import SentenceAssignment, ShotMatch, ShotRef
from edit.shot_match_llm import StaticShotMatchOrchestrator
from vlm.schema import Clip, IdentifiedShot, Provider, TwelveLabsClipRef, VlmAnalysis


def _mini_analysis() -> VlmAnalysis:
    shot = IdentifiedShot(
        shotId="m1",
        startSec=0.0,
        endSec=4.0,
        vlmTag="the_interaction",
        keyInstantStartSec=2.0,
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


def test_static_shot_match_orchestrator():
    analysis = _mini_analysis()
    ledger = SentenceLedger(
        sentences=[
            SentenceEntry(
                sentenceId="s0",
                text="Hi.",
                speechStartSec=0.0,
                speechEndSec=0.55,
                beatCount=1,
            ),
        ]
    )

    fake = ShotMatch(
        _planning="Static mock planning for one sentence.",
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                text="Hi.",
                shots=[
                    ShotRef(
                        clipId="c0",
                        shotId="m1",
                        beatSpan=1,
                        reasoning="Matches the greeting beat.",
                    )
                ],
            ),
        ],
    )

    orch = StaticShotMatchOrchestrator(fake)
    out = orch.generate_shot_match(analysis=analysis, ledger=ledger)
    assert out.model_dump() == fake.model_dump()
