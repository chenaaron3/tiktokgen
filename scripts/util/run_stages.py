"""Canonical pipeline stage directory names under a Run."""

from __future__ import annotations

from enum import StrEnum


class RunStage(StrEnum):
    SCRIPT = "1_script"
    VLM = "2_vlm"
    TTS = "3_tts"
    WHISPER = "4_whisper"
    SENTENCE_LEDGER = "5_sentence_ledger"
    MATCH = "6_match"
    ASSEMBLE = "7_assemble"
    RENDER = "8_render"
