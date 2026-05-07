"""VLM analysis module exports."""

from __future__ import annotations

from typing import Any

from .media import discover_videos, probe_media
from .schema import Clip, IdentifiedShot, Provider, TwelveLabsClipRef, VlmAnalysis
from .twelvelabs import TwelveLabsVideoAnalyzer

__all__ = [
    "Clip",
    "IdentifiedShot",
    "Provider",
    "TwelveLabsClipRef",
    "TwelveLabsVideoAnalyzer",
    "VlmAnalysis",
    "discover_videos",
    "probe_media",
    "run_analysis",
]


def __getattr__(name: str) -> Any:
    if name == "run_analysis":
        from .analysis import run as run_analysis

        return run_analysis
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
