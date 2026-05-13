"""In-memory fakes for chaining pipeline steps in unit tests."""

from __future__ import annotations

from pathlib import Path

from contracts import WordToken
from narrative.providers import ScriptGenerator, TextToSpeech, WordTranscriber
from util import PathUtil


class StaticScriptGenerator(ScriptGenerator):
    def __init__(self, script: str) -> None:
        self._script = script

    def generate(self, notes: str, *, use_cache: bool = True) -> tuple[str, str]:
        return "", self._script


class StaticTts(TextToSpeech):
    """Returns the nominal voice path without touching disk."""

    def __init__(self, paths: PathUtil) -> None:
        self._paths = paths

    def synthesize(self, script_text: str, *, use_cache: bool = True) -> Path:
        return self._paths.voiceover_mp3()


class StaticWordTranscriber(WordTranscriber):
    """Returns predefined tokens in memory only."""

    def __init__(self, words: list[WordToken]) -> None:
        self._words = words

    def transcribe_words(self, *, use_cache: bool = True) -> list[WordToken]:
        return [w.model_copy(deep=True) for w in self._words]
