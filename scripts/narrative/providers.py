"""Protocols for script, TTS, and word transcription (mock in tests)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from contracts import WordToken


@runtime_checkable
class ScriptGenerator(Protocol):
    def generate(self, notes: str) -> str:
        """Return spoken script body (may load from cached ``script.txt``, call an LLM, or echo a stub)."""
        ...


@runtime_checkable
class TextToSpeech(Protocol):
    def synthesize(self, script_text: str) -> Path:
        ...


@runtime_checkable
class WordTranscriber(Protocol):
    def transcribe_words(self) -> list[WordToken]:
        """Decode word timings under one run layout (typically idempotent cached JSON)."""
        ...
