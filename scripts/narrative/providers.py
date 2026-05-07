"""Protocols for script, TTS, and word transcription (mock in tests)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from contracts import WordToken


@runtime_checkable
class ScriptGenerator(Protocol):
    def generate(self, notes: str) -> str:
        """Return approved-style script text (spoken)."""
        ...


@runtime_checkable
class TextToSpeech(Protocol):
    def synthesize(self, script_text: str, output_mp3: Path) -> None:
        ...


@runtime_checkable
class WordTranscriber(Protocol):
    def transcribe_words(self, audio_mp3: Path) -> list[WordToken]:
        ...
