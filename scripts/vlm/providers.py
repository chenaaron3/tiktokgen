"""Injectable VLM backends (mock TwelveLabs in tests)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class VideoAnalysisBackend(Protocol):
    def analyze(
        self,
        *,
        source: Path,
        cache_dir: Path,
        output_dir: Path | None,
        recursive: bool,
        model: str,
        min_segment_duration: float,
        max_segment_duration: float,
        max_concurrency: int,
    ) -> Path:
        """Return run directory containing `vlm-analysis.json`."""
        ...


class TwelveLabsVideoAnalysisBackend:
    """Default TwelveLabs pipeline."""

    def analyze(
        self,
        *,
        source: Path,
        cache_dir: Path,
        output_dir: Path | None,
        recursive: bool,
        model: str,
        min_segment_duration: float,
        max_segment_duration: float,
        max_concurrency: int,
    ) -> Path:
        from vlm.analysis import run as run_analysis

        return run_analysis(
            source=source,
            cache_dir=cache_dir,
            output_dir=output_dir,
            recursive=recursive,
            model=model,
            min_segment_duration=min_segment_duration,
            max_segment_duration=max_segment_duration,
            max_concurrency=max_concurrency,
        )
