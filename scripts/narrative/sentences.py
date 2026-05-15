"""Sentence windows + beat counts from word-level transcription."""

from __future__ import annotations

import re

from contracts import SentenceEntry, SentenceLedger, WordToken, sentence_beat_count
from util import PathUtil, read_json_model, write_json_model

_SENTENCE_END = re.compile(r"[.!?]\s*$")


def build_sentence_ledger(
    words: list[WordToken],
    audio_duration_sec: float,
    paths: PathUtil | None = None,
    *,
    use_cache: bool = True,
) -> SentenceLedger:
    """Group words into sentences and normalize to span ``[0, audio_duration_sec]``.

    When ``paths`` is set, writes ``sentence-ledger.json`` under the run directory.
    """
    if paths is not None:
        ledger_path = paths.sentence_ledger_json()
        cached = read_json_model(ledger_path, SentenceLedger, use_cache=use_cache)
        if cached is not None:
            return cached

    if audio_duration_sec <= 0:
        raise ValueError("audio_duration_sec must be positive")
    if not words:
        raise ValueError("cannot build sentence ledger from empty words")

    sentence_texts: list[str] = []
    sentence_word_end_secs: list[float] = []
    buffer: list[WordToken] = []

    def flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        text = " ".join(w.word.strip() for w in buffer).strip()
        if not text:
            buffer = []
            return
        sentence_texts.append(text)
        sentence_word_end_secs.append(buffer[-1].end_sec)
        buffer = []

    for w in words:
        buffer.append(w)
        if _SENTENCE_END.search(w.word.strip()):
            flush()

    flush()
    if not sentence_texts:
        raise ValueError("cannot build sentence ledger from empty sentence text")
    if sentence_word_end_secs[-1] > audio_duration_sec + 1e-6:
        raise ValueError(
            "audio_duration_sec must be >= end of last transcribed word: "
            f"{audio_duration_sec:.6f} < {sentence_word_end_secs[-1]:.6f}"
        )

    sentences: list[SentenceEntry] = []
    prev_end = 0.0
    for idx, text in enumerate(sentence_texts):
        start = prev_end
        if idx == len(sentence_texts) - 1:
            end = audio_duration_sec
        else:
            end = sentence_word_end_secs[idx]
        if end < start:
            raise ValueError(
                f"sentence window must be non-decreasing (sentence s{idx}: {start:.6f} -> {end:.6f})"
            )
        duration = max(1e-9, end - start)
        beat_count = sentence_beat_count(duration)
        sentences.append(
            SentenceEntry(
                sentenceId=f"s{idx}",
                text=text,
                speechStartSec=start,
                speechEndSec=end,
                beatCount=beat_count,
            )
        )
        prev_end = end

    ledger = SentenceLedger(sentences=sentences)
    if paths is not None:
        write_json_model(paths.sentence_ledger_json(), ledger)
    return ledger
