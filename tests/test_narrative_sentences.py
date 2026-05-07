import pytest

from contracts import WordToken
from narrative.sentences import build_sentence_ledger


def test_sentence_ledger_end_to_end_fixture_chain():
    words = [
        WordToken(word="One", startSec=0.0, endSec=0.15),
        WordToken(word="two", startSec=0.15, endSec=0.35),
        WordToken(word="three.", startSec=0.35, endSec=0.55),
        WordToken(word="Next!", startSec=1.5, endSec=1.9),
    ]
    ledger = build_sentence_ledger(words)
    assert len(ledger.sentences) == 2
    assert ledger.sentences[0].beat_count >= 1
    assert ledger.sentences[1].sentence_id == "s1"
    assert ledger.sentences[1].speech_start_sec == pytest.approx(1.5)
