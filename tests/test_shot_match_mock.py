"""Shot-match façade with deterministic orchestrator (no LiteLLM)."""

from contracts import SentenceEntry, SentenceLedger
from edit.planner_facade import run_shot_match
from edit.schema_shot_match import SentenceAssignment, ShotMatch, ShotRef, ShotSentenceLine
from edit.shot_match_llm import StaticShotMatchOrchestrator
from vlm.schema import Clip, IdentifiedShot, Provider, TwelveLabsClipRef, VlmAnalysis


def _mini_analysis() -> VlmAnalysis:
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


def test_run_shot_match_uses_mock_orchestrator():
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
        schemaVersion="0.2.0",
        sentences=[ShotSentenceLine(sentenceId="s0", text="Hi.")],
        assignments=[
            SentenceAssignment(
                sentenceId="s0",
                shots=[ShotRef(clipId="c0", momentId="m1")],
            ),
        ],
    )

    orch = StaticShotMatchOrchestrator(fake)
    out = run_shot_match(
        analysis=analysis,
        ledger=ledger,
        orchestrator=orch,
        guidance=None,
        model=None,
        observability_path=None,
    )
    assert out.model_dump() == fake.model_dump()
