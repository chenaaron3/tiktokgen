"""Mock-friendly artifacts for chaining: words → ledger → … → assemble."""

from __future__ import annotations

from contracts import WordToken
from edit.schema_shot_match import SentenceAssignment, ShotMatch, ShotRef, ShotSentenceLine

# Pass into narrative.build_sentence_ledger
PIPELINE_SAMPLE_WORDS: list[WordToken] = [
    WordToken(word="Great", startSec=0.0, endSec=0.22),
    WordToken(word="bite.", startSec=0.22, endSec=0.72),
]

# Example shot-match pairing one sentence ↔ one `(clipId, momentId)`
PIPELINE_SAMPLE_SHOT_MATCH = ShotMatch(
    schemaVersion="0.2.0",
    sentences=[ShotSentenceLine(sentenceId="s0", text="Great bite.")],
    assignments=[
        SentenceAssignment(
            sentenceId="s0",
            shots=[ShotRef(clipId="fixture-clip-id", momentId="fixture-moment-id")],
        ),
    ],
)

__all__ = ["PIPELINE_SAMPLE_SHOT_MATCH", "PIPELINE_SAMPLE_WORDS"]
