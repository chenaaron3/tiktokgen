from pathlib import Path

from vlm.providers import VideoAnalysisBackend


class FakeVlmBackend:
    """Implements VideoAnalysisBackend without hitting TwelveLabs (use in tests)."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir

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
        target = output_dir or (cache_dir / "fake-run")
        target.mkdir(parents=True, exist_ok=True)
        (target / ".fake-vlm-marker").write_text("ok")
        self.run_dir = target
        return target


def test_protocol_runtime_check():
    backend: VideoAnalysisBackend = FakeVlmBackend(Path("/tmp"))
    assert isinstance(backend, VideoAnalysisBackend)
