"""Sentence windows + beat counts from word-level transcription."""

from __future__ import annotations

import math
import re

from contracts import SentenceEntry, SentenceLedger, WordToken

_SENTENCE_END = re.compile(r"[.!?]\s*$")


def build_sentence_ledger(words: list[WordToken]) -> SentenceLedger:
    """Group words into sentences ending in . ! ? and compute ceil-duration beats."""
    if not words:
        return SentenceLedger(sentences=[])

    sentences: list[SentenceEntry] = []
    buffer: list[WordToken] = []

    def flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        idx = len(sentences)
        text = " ".join(w.word.strip() for w in buffer).strip()
        if not text:
            buffer = []
            return
        start = buffer[0].start_sec
        end = buffer[-1].end_sec
        duration = max(1e-9, end - start)
        beat_count = max(1, math.ceil(duration - 1e-12))
        sentences.append(
            SentenceEntry(
                sentenceId=f"s{idx}",
                text=text,
                speechStartSec=start,
                speechEndSec=end,
                beatCount=beat_count,
            )
        )
        buffer = []

    for w in words:
        buffer.append(w)
        if _SENTENCE_END.search(w.word.strip()):
            flush()

    flush()
    return SentenceLedger(sentences=sentences)
