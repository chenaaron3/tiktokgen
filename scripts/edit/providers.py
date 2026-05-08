"""Injectable LLM backend for shot matching (unit tests use a fake)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contracts import SentenceLedger
from edit.schema_shot_match import ShotMatch
from vlm.schema import VlmAnalysis


@runtime_checkable
class ShotMatchOrchestrator(Protocol):
    def generate_shot_match(
        self,
        *,
        analysis: VlmAnalysis,
        ledger: SentenceLedger,
        guidance: str | None,
    ) -> ShotMatch: ...
