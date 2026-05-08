"""VLM backend protocol conformance (unit tests only)."""

from __future__ import annotations

import json
from pathlib import Path

from util import PathUtil
from vlm.providers import VideoAnalysisBackend
from vlm.schema import VlmAnalysis


def _minimal_fake_analysis(source: Path) -> dict:
    clip = {
        "id": "fake",
        "sourcePath": str(source),
        "originalFilename": source.name if source.name else "clip.mov",
        "durationSec": 1.0,
        "capturedAt": None,
        "location": None,
        "media": {},
        "twelveLabs": {"assetId": "fake-asset", "taskId": "fake-task"},
        "summary": "fake summary",
        "identifiedShots": [
            {
                "shotId": "shot-001",
                "startSec": 0.0,
                "endSec": 1.0,
                "vlmTag": "not_suitable",
                "confidenceScore": 0.5,
                "keyInstantSec": 0.5,
                "reasoning": "fake",
            }
        ],
    }
    return {
        "runId": "fake-run",
        "analyzedAt": "2026-01-01T00:00:00+00:00",
        "provider": {"name": "fake", "model": "fake", "rawResponseRef": "stub"},
        "clips": [clip],
    }


class FakeVlmBackend:
    """Implements VideoAnalysisBackend without hitting TwelveLabs (use in tests)."""

    def __init__(self, run_dir: Path) -> None:
        self._paths = PathUtil(run_dir)

    def analyze(self, source: Path) -> VlmAnalysis:
        vlm_path = self._paths.vlm_analysis_json()
        if vlm_path.is_file():
            return VlmAnalysis.model_validate(json.loads(vlm_path.read_text()))
        vlm_path.parent.mkdir(parents=True, exist_ok=True)
        blob = json.dumps(_minimal_fake_analysis(source), indent=2) + "\n"
        vlm_path.write_text(blob)
        return VlmAnalysis.model_validate(json.loads(blob))


def test_protocol_runtime_check():
    backend: VideoAnalysisBackend = FakeVlmBackend(Path("/tmp"))
    assert isinstance(backend, VideoAnalysisBackend)
