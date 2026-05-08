"""Sentence windows + beat counts from word-level transcription."""

from __future__ import annotations

import json
import math
import re

from contracts import SentenceEntry, SentenceLedger, WordToken
from util import PathUtil

_SENTENCE_END = re.compile(r"[.!?]\s*$")


def build_sentence_ledger(words: list[WordToken], paths: PathUtil | None = None) -> SentenceLedger:
    """Group words into sentences ending in . ! ? and compute ceil-duration beats.

    When ``paths`` is set, writes ``sentence-ledger.json`` under the run directory.
    """
    if not words:
        ledger = SentenceLedger(sentences=[])
        if paths is not None:
            ledger_path = paths.sentence_ledger_json()
            ledger_path.write_text(json.dumps(ledger.model_dump(by_alias=True), indent=2) + "\n")
        return ledger

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
    ledger = SentenceLedger(sentences=sentences)
    if paths is not None:
        ledger_path = paths.sentence_ledger_json()
        ledger_path.write_text(json.dumps(ledger.model_dump(by_alias=True), indent=2) + "\n")
    return ledger
