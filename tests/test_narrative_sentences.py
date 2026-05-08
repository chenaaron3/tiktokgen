import pytest

from contracts import WordToken, sentence_beat_count
from narrative.sentences import build_sentence_ledger


def test_sentence_ledger_end_to_end_fixture_chain():
    words = [
        WordToken(word="One", startSec=0.0, endSec=0.15),
        WordToken(word="two", startSec=0.15, endSec=0.35),
        WordToken(word="three.", startSec=0.35, endSec=0.55),
        WordToken(word="Next!", startSec=1.5, endSec=1.9),
    ]
    ledger = build_sentence_ledger(words, audio_duration_sec=2.1)
    assert len(ledger.sentences) == 2
    assert ledger.sentences[0].beat_count == 1
    assert ledger.sentences[1].beat_count == 1
    assert ledger.sentences[1].sentence_id == "s1"
    assert ledger.sentences[0].speech_start_sec == pytest.approx(0.0)
    assert ledger.sentences[1].speech_start_sec == pytest.approx(0.55)
    assert ledger.sentences[1].speech_end_sec == pytest.approx(2.1)


def test_sentence_ledger_with_many_sentences_is_contiguous_and_covers_audio():
    words = [
        WordToken(word="One.", startSec=0.0, endSec=0.2),
        WordToken(word="Two.", startSec=0.6, endSec=0.9),
        WordToken(word="Three", startSec=1.2, endSec=1.35),
        WordToken(word="part.", startSec=1.35, endSec=1.7),
        WordToken(word="Four!", startSec=2.0, endSec=2.4),
        WordToken(word="Five?", startSec=2.9, endSec=3.25),
    ]
    ledger = build_sentence_ledger(words, audio_duration_sec=3.6)
    assert len(ledger.sentences) == 5
    assert [s.sentence_id for s in ledger.sentences] == ["s0", "s1", "s2", "s3", "s4"]
    assert [s.text for s in ledger.sentences] == ["One.", "Two.", "Three part.", "Four!", "Five?"]
    assert ledger.sentences[0].speech_start_sec == pytest.approx(0.0)
    assert ledger.sentences[-1].speech_end_sec == pytest.approx(3.6)

    for i in range(1, len(ledger.sentences)):
        assert ledger.sentences[i].speech_start_sec == pytest.approx(
            ledger.sentences[i - 1].speech_end_sec
        )


def test_sentence_ledger_raises_on_empty_words():
    with pytest.raises(ValueError, match="empty words"):
        build_sentence_ledger([], audio_duration_sec=1.0)


def test_sentence_beat_count_ceil_per_target_seconds():
    assert sentence_beat_count(0.55) == 1
    assert sentence_beat_count(2.0) == 1
    assert sentence_beat_count(2.01) == 2
    assert sentence_beat_count(4.1) == 3
