"""Ensure checked-in fixture objects stay structurally valid."""

from fixtures.pipeline import PIPELINE_SAMPLE_SHOT_MATCH, PIPELINE_SAMPLE_WORDS
from narrative.sentences import build_sentence_ledger


def test_fixture_words_produce_ledger():
    ledger = build_sentence_ledger(PIPELINE_SAMPLE_WORDS, audio_duration_sec=0.72)
    assert ledger.sentences and ledger.sentences[0].beat_count >= 1


def test_fixture_shot_match_validates():
    assert PIPELINE_SAMPLE_SHOT_MATCH.assignments
