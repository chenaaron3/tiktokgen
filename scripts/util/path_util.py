"""Filesystem paths: pipeline run layout, bundled footage + notes, and TwelveLabs dirs."""

from __future__ import annotations

from pathlib import Path

from project_inputs import resolve_project_path


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

    def vlm_output_dir(self) -> Path:
        """Directory where ``vlm-analysis.json`` for this pipeline run should be written."""
        return self._stage_dir("2_vlm")

    def llm_observability_dir(self) -> Path:
        return self._run_dir / "llm-observability"

    def _stage_dir(self, stage: str) -> Path:
        path = self._run_dir / stage
        path.mkdir(parents=True, exist_ok=True)
        return path

    def script_draft_txt(self) -> Path:
        return self._stage_dir("1_script") / "script.draft.txt"

    def script_txt(self) -> Path:
        return self._stage_dir("1_script") / "script.txt"

    def script_llm_observability_json(self) -> Path:
        return self.llm_observability_dir() / "script.json"

    def vlm_analysis_json(self) -> Path:
        return self._stage_dir("2_vlm") / "vlm-analysis.json"

    def voiceover_mp3(self) -> Path:
        return self._stage_dir("3_tts") / "voiceover.mp3"

    def whisper_words_json(self) -> Path:
        return self._stage_dir("4_whisper") / "whisper-words.json"

    def sentence_ledger_json(self) -> Path:
        return self._stage_dir("5_sentence_ledger") / "sentence-ledger.json"

    def shot_match_json(self) -> Path:
        return self._stage_dir("6_match") / "shot-match.json"

    def shot_match_llm_observability_json(self) -> Path:
        return self.llm_observability_dir() / "shot-match.json"

    def render_plan_json(self) -> Path:
        return self._stage_dir("7_assemble") / "render-plan.json"

    def default_render_mp4(self) -> Path:
        return self._stage_dir("8_render") / "render.mp4"


def pick_notes_txt(project_dir: Path) -> Path | None:
    """Return ``project_dir/notes.txt`` if that file exists; otherwise ``None``."""
    project_dir = project_dir.resolve()
    path = project_dir / "notes.txt"
    return path.resolve() if path.is_file() else None


def resolve_bundled_project(source: Path) -> tuple[Path, Path]:
    """
    Resolve ``source`` to a bundled project folder: videos for VLM plus ``notes.txt`` (exact name).

    Relative paths resolve under ``PROJECT_ROOT`` (see ``resolve_project_path``).

    Returns ``(footage_root, notes_path)`` for VLM + script generation.
    """
    from vlm.media import discover_videos

    resolved_root = resolve_project_path(source)
    if resolved_root.is_file():
        raise SystemExit(
            "SOURCE must be a **project directory** (videos + notes.txt alongside), not a single file. "
            "Put clips and notes.txt in one folder and pass that path—for example assets/2026-05-03."
        )
    if not resolved_root.is_dir():
        raise SystemExit(
            f"Bundled mode expects a directory with videos + notes.txt: not a directory ({resolved_root})."
        )

    notes = pick_notes_txt(resolved_root)
    if notes is None:
        raise SystemExit(
            f"Bundled mode requires {resolved_root / 'notes.txt'}. "
            "Create that file (exact name) in the project folder beside your clips."
        )

    try:
        discover_videos(resolved_root)
    except FileNotFoundError as error:
        raise SystemExit(str(error)) from None
    except ValueError as error:
        raise SystemExit(str(error)) from None

    return resolved_root, notes
