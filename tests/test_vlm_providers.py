"""VLM backend protocol conformance (unit tests only)."""

from __future__ import annotations

import json
from pathlib import Path

from util import PathUtil, read_json_model, write_json_model
from vlm.analysis import run as run_vlm_analysis
from vlm.notes import ParsedReviewNotes
from vlm.providers import VideoAnalysisBackend
from vlm.schema import VlmAnalysis


def _minimal_fake_analysis(source: Path) -> VlmAnalysis:
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
                "keyInstantStartSec": 0.5,
                "reasoning": "fake",
            }
        ],
    }
    return VlmAnalysis.model_validate(
        {
            "runId": "fake-run",
            "analyzedAt": "2026-01-01T00:00:00+00:00",
            "provider": {"name": "fake", "model": "fake", "rawResponseRef": "stub"},
            "clips": [clip],
        }
    )


class FakeVlmBackend:
    """Implements VideoAnalysisBackend without hitting TwelveLabs (use in tests)."""

    def __init__(self, run_dir: Path) -> None:
        self._paths = PathUtil(run_dir)

    def analyze(
        self,
        source: Path,
        additional_context: ParsedReviewNotes | None = None,
        use_cache: bool = True,
    ) -> VlmAnalysis:
        vlm_path = self._paths.vlm_analysis_json()
        cached = read_json_model(vlm_path, VlmAnalysis, use_cache=use_cache)
        if cached is not None:
            return cached
        analysis = _minimal_fake_analysis(source)
        write_json_model(vlm_path, analysis)
        return analysis


def test_protocol_runtime_check():
    backend: VideoAnalysisBackend = FakeVlmBackend(Path("/tmp"))
    assert isinstance(backend, VideoAnalysisBackend)


def test_run_vlm_analysis_uses_cache(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    vlm_dir = run_dir / "2_vlm"
    vlm_dir.mkdir(parents=True)
    analysis_path = vlm_dir / "vlm-analysis.json"
    fake = _minimal_fake_analysis(tmp_path / "clip.mov")
    write_json_model(analysis_path, fake)

    out = run_vlm_analysis(
        source=tmp_path,
        output_dir=vlm_dir,
        use_cache=True,
    )
    assert out == vlm_dir
    assert VlmAnalysis.model_validate(json.loads(analysis_path.read_text())).run_id == "fake-run"
