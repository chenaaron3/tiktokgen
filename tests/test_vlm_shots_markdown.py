from contracts import SentenceEntry, SentenceLedger
from edit.vlm_shots import (
    format_sentences_markdown,
    format_shot_match_user_message,
    format_vlm_shots_markdown,
)
from vlm.schema import Clip, ClipMedia, IdentifiedShot, Provider, TwelveLabsClipRef, VlmAnalysis


def _shot(
    *,
    shot_id: str,
    tag: str,
    dish: str | None = None,
    reasoning: str = "reason",
) -> IdentifiedShot:
    return IdentifiedShot(
        shotId=shot_id,
        startSec=0.0,
        endSec=3.0,
        vlmTag=tag,
        keyInstantStartSec=1.0,
        dishName=dish,
        reasoning=reasoning,
        labelConfidence="high",
        verifiedBy="twelvelabs",
    )


def _analysis(*shots: IdentifiedShot) -> VlmAnalysis:
    clip = Clip(
        id="CLIP_A",
        sourcePath="/tmp/a.mov",
        originalFilename="a.mov",
        durationSec=10.0,
        capturedAt=None,
        location=None,
        media=ClipMedia.empty(),
        twelveLabs=TwelveLabsClipRef(assetId="a", taskId="t"),
        summary="s",
        identifiedShots=list(shots),
    )
    return VlmAnalysis(
        runId="r",
        analyzedAt="t",
        provider=Provider(name="p", model="m", rawResponseRef=""),
        clips=[clip],
    )


def test_format_vlm_shots_markdown_groups_general_and_dish():
    analysis = _analysis(
        _shot(shot_id="shot-001", tag="establishing_exterior", reasoning="Facade."),
        _shot(shot_id="shot-002", tag="the_interaction", dish="Ramen", reasoning="Lift noodles."),
    )
    markdown = format_vlm_shots_markdown(analysis)
    assert "# Shot catalog" in markdown
    assert "## General shots" in markdown
    assert "### CLIP_A / shot-001" in markdown
    assert "- tag: establishing_exterior" in markdown
    assert "## Dish: Ramen" in markdown
    assert "### CLIP_A / shot-002" in markdown


def test_format_vlm_shots_markdown_excludes_not_suitable():
    analysis = _analysis(
        _shot(shot_id="shot-001", tag="not_suitable", reasoning="Blurry."),
        _shot(shot_id="shot-002", tag="texture_macro", reasoning="Macro."),
    )
    markdown = format_vlm_shots_markdown(analysis)
    assert "not_suitable" not in markdown
    assert "shot-001" not in markdown
    assert "shot-002" in markdown
    assert "texture_macro" in markdown


def test_format_sentences_markdown_orders_narration():
    ledger = SentenceLedger(
        sentences=[
            SentenceEntry(
                sentenceId="s0",
                text="Hook line.",
                speechStartSec=0.0,
                speechEndSec=3.0,
                beatCount=2,
            ),
            SentenceEntry(
                sentenceId="s1",
                text="Second line.",
                speechStartSec=3.0,
                speechEndSec=6.0,
                beatCount=2,
            ),
        ]
    )
    markdown = format_sentences_markdown(ledger)
    assert "# Narration" in markdown
    assert "### s0 (hook)" in markdown
    assert "- text: Hook line." in markdown
    assert "- beatCount: 2" in markdown
    assert "- speech: 0.0s – 3.0s" in markdown
    assert "### s1" in markdown
    assert "hook" not in "### s1"


def test_format_shot_match_user_message_concatenates_sections():
    ledger = SentenceLedger(
        sentences=[
            SentenceEntry(
                sentenceId="s0",
                text="Line.",
                speechStartSec=0.0,
                speechEndSec=2.0,
                beatCount=1,
            ),
        ]
    )
    analysis = _analysis(_shot(shot_id="shot-001", tag="texture_macro"))
    message = format_shot_match_user_message(ledger=ledger, analysis=analysis)
    assert message.index("# Narration") < message.index("# Shot catalog")
