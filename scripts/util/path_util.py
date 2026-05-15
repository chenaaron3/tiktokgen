"""Filesystem paths for one pipeline Run artifact tree."""

from __future__ import annotations

from pathlib import Path

from util.run_stages import RunStage


class PathUtil:
    """Resolved artifact paths under one pipeline run directory."""

    __slots__ = ("_run_dir",)

    def __init__(self, run_dir: Path) -> None:
        self._run_dir = run_dir

    @property
    def run_dir(self) -> Path:
        return self._run_dir

    def vlm_cache_dir(self) -> Path:
        """Parent of the run directory (e.g. ``cache/``), used for sibling runs when output is explicit."""
        return self._run_dir.parent

    def llm_observability_dir(self) -> Path:
        return self._run_dir / "llm-observability"

    def stage_dir(self, stage: RunStage) -> Path:
        path = self._run_dir / stage.value
        path.mkdir(parents=True, exist_ok=True)
        return path

    def vlm_output_dir(self) -> Path:
        return self.stage_dir(RunStage.VLM)

    def script_draft_txt(self) -> Path:
        return self.stage_dir(RunStage.SCRIPT) / "script.draft.txt"

    def script_txt(self) -> Path:
        return self.stage_dir(RunStage.SCRIPT) / "script.txt"

    def script_llm_observability_json(self) -> Path:
        return self.llm_observability_dir() / "script.json"

    def vlm_analysis_json(self) -> Path:
        return self.stage_dir(RunStage.VLM) / "vlm-analysis.json"

    def vlm_verify_frames_dir(self) -> Path:
        path = self.stage_dir(RunStage.VLM) / "verify-frames"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def vlm_verify_llm_observability_json(self, clip_id: str, shot_id: str) -> Path:
        name = f"{clip_id}-{shot_id}"
        safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in name).strip("-")
        if not safe:
            safe = "vlm-verify"
        self.llm_observability_dir().mkdir(parents=True, exist_ok=True)
        return self.llm_observability_dir() / f"vlm-verify-{safe}.json"

    def voiceover_mp3(self) -> Path:
        return self.stage_dir(RunStage.TTS) / "voiceover.mp3"

    def whisper_words_json(self) -> Path:
        return self.stage_dir(RunStage.WHISPER) / "whisper-words.json"

    def sentence_ledger_json(self) -> Path:
        return self.stage_dir(RunStage.SENTENCE_LEDGER) / "sentence-ledger.json"

    def shot_match_json(self) -> Path:
        return self.stage_dir(RunStage.MATCH) / "shot-match.json"

    def shot_match_llm_observability_json(self) -> Path:
        return self.llm_observability_dir() / "shot-match.json"

    def render_plan_json(self) -> Path:
        return self.stage_dir(RunStage.ASSEMBLE) / "render-plan.json"

    def default_render_mp4(self) -> Path:
        return self.stage_dir(RunStage.RENDER) / "render.mp4"
