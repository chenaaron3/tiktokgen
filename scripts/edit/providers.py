"""Injectable LLM backend for shot matching (unit tests use a fake)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from edit.schema_shot_match import ShotMatch


@runtime_checkable
class ShotMatchOrchestrator(Protocol):
    def generate_shot_match(
        self,
        *,
        sentences: list[dict[str, Any]],
        vlm_shots: list[dict[str, Any]],
        guidance: str | None,
    ) -> ShotMatch: ...
