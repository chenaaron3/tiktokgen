"""Injectable VLM backends (mock TwelveLabs in tests)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from util import PathUtil

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
        """Load cached ``vlm-analysis.json`` under the run paths, or analyze ``source`` and return it."""
        ...


class TwelveLabsVideoAnalysisBackend:
    """Default TwelveLabs pipeline (segment durations, model, concurrency: ``vlm.analysis.run`` defaults)."""

    def __init__(self, paths: PathUtil) -> None:
        self._paths = paths

    def analyze(
        self,
        source: Path,
        additional_context: ParsedReviewNotes | None = None,
        use_cache: bool = True,
    ) -> VlmAnalysis:
        out = self._paths.vlm_analysis_json()
        if use_cache and out.is_file():
            return VlmAnalysis.model_validate(json.loads(out.read_text()))

        print("\n==> VLM analyze")
        from vlm.analysis import run as run_analysis

        run_analysis(
            source=source,
            cache_dir=self._paths.vlm_cache_dir(),
            output_dir=self._paths.vlm_output_dir(),
            additional_context=additional_context,
        )
        return VlmAnalysis.model_validate(json.loads(out.read_text()))
