"""Injectable VLM backends (mock in tests)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from .notes import ParsedReviewNotes
from .schema import VlmAnalysis


@runtime_checkable
class VideoAnalysisBackend(Protocol):
    def analyze(
        self,
        source: Path,
        additional_context: ParsedReviewNotes | None = None,
        use_cache: bool = True,
    ) -> VlmAnalysis:
        """Return normalized VLM analysis for ``source`` (cache when ``use_cache``)."""
        ...
