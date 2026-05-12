"""Mock-friendly artifacts for chaining: words → ledger → … → assemble."""

from __future__ import annotations

from contracts import WordToken
from edit.schema_shot_match import SentenceAssignment, ShotMatch, ShotRef

# Pass into narrative.build_sentence_ledger
PIPELINE_SAMPLE_WORDS: list[WordToken] = [
    WordToken(word="Great", startSec=0.0, endSec=0.22),
    WordToken(word="bite.", startSec=0.22, endSec=0.72),
]

# Example shot-match pairing one sentence ↔ one `(clipId, shotId)`
PIPELINE_SAMPLE_SHOT_MATCH = ShotMatch(
    _planning="Fixture planning: one sentence uses one shot.",
    assignments=[
        SentenceAssignment(
            sentenceId="s0",
            text="Great bite.",
            shots=[
                ShotRef(
                    clipId="fixture-clip-id",
                    shotId="fixture-shot-id",
                    reasoning="Shows the bite to support the narration.",
                )
            ],
        ),
    ],
)

__all__ = ["PIPELINE_SAMPLE_SHOT_MATCH", "PIPELINE_SAMPLE_WORDS"]
