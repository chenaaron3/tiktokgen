"""In-memory fakes for chaining pipeline steps in unit tests."""

from __future__ import annotations

from pathlib import Path

from contracts import WordToken
from narrative.providers import ScriptGenerator, TextToSpeech, WordTranscriber


class StaticScriptGenerator(ScriptGenerator):
    def __init__(self, script: str) -> None:
        self._script = script

    def generate(self, notes: str) -> str:
        return self._script


class StaticTts(TextToSpeech):
    """Writes a tiny placeholder file (not a valid MP3—only for I/O mocks)."""

    def __init__(self, marker: bytes = b"UNITTEST_TTS") -> None:
        self._marker = marker

    def synthesize(self, script_text: str, output_mp3: Path) -> None:
        output_mp3.parent.mkdir(parents=True, exist_ok=True)
        output_mp3.write_bytes(self._marker)


class StaticWordTranscriber(WordTranscriber):
    """Returns predefined tokens without reading audio."""

    def __init__(self, words: list[WordToken]) -> None:
        self._words = words

    def transcribe_words(self, audio_mp3: Path) -> list[WordToken]:
        return [w.model_copy(deep=True) for w in self._words]
