#!/usr/bin/env python3
"""Orchestrate VLM analysis, narration (script/TTS/whisper), shot-match, assembly, Remotion."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path

from dotenv import load_dotenv
from edit import LitellmAgentReviewOrchestrator, LitellmShotMatchOrchestrator
from edit.assemble import assemble_render_plan, build_resolved_sentences
from narrative import (
    ElevenLabsTts,
    FasterWhisperWordTranscriber,
    LitellmScriptGenerator,
    build_sentence_ledger,
)
from pydantic import ValidationError
from project_inputs import PROJECT_ROOT, resolve_run_directory
from util import PathUtil, resolve_bundled_project
from util.render import run_remotion_render
from vlm import TwelveLabsVideoAnalysisBackend
from vlm.notes import parse_review_notes
from vlm.media import probe_media

class PipelineStep(StrEnum):
    VLM = "vlm"
    SCRIPT = "script"
    TTS = "tts"
    WHISPER = "whisper"
    SENTENCE_LEDGER = "sentence_ledger"
    MATCH = "match"
    AGENT_REVIEW = "agent_review"
    ASSEMBLE = "assemble"
    RENDER = "render"


_STEP_ORDER: dict[PipelineStep, int] = {
    PipelineStep.VLM: 1,
    PipelineStep.SCRIPT: 2,
    PipelineStep.TTS: 3,
    PipelineStep.WHISPER: 4,
    PipelineStep.SENTENCE_LEDGER: 5,
    PipelineStep.MATCH: 6,
    PipelineStep.AGENT_REVIEW: 7,
    PipelineStep.ASSEMBLE: 8,
    PipelineStep.RENDER: 9,
}
_BREAK_STEPS: tuple[PipelineStep, ...] = (
    PipelineStep.VLM,
    PipelineStep.SCRIPT,
    PipelineStep.TTS,
    PipelineStep.MATCH,
    PipelineStep.AGENT_REVIEW,
    PipelineStep.ASSEMBLE,
)
_RERUN_STEPS: tuple[PipelineStep, ...] = tuple(PipelineStep)


def should_use_cache(*, step: PipelineStep, rerun_from: PipelineStep | None) -> bool:
    """Return False for rerun step and all downstream steps."""
    if rerun_from is None:
        return True
    return _STEP_ORDER[step] < _STEP_ORDER[rerun_from]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Narrative short pipeline: VLM + script/TTS/whisper + shot-match LLM + Remotion render."
        ),
    )
    parser.add_argument(
        "source",
        type=Path,
        help=(
            "Bundled **project folder**: videos for VLM plus **notes.yaml** (exact filename) "
            "in that same directory."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("cache"),
        help="Base directory for source-keyed run folders (default: cache/).",
    )
    parser.add_argument(
        "--break",
        dest="break_after",
        metavar="STEP",
        type=PipelineStep,
        choices=_BREAK_STEPS,
        default=None,
        help=(
            "Exit successfully right after this pipeline step. "
            "Steps: vlm (after VLM analysis), script (after script.txt), "
            "tts (after voice synthesize only; Whisper and later skipped on this run), "
            "match (after shot-match.json), "
            "agent_review (after agentic review loop finalizes shot-match.json), "
            "assemble (after render-plan.json; Remotion render skipped)."
        ),
    )
    parser.add_argument(
        "--from",
        dest="rerun_from",
        metavar="STEP",
        type=PipelineStep,
        choices=_RERUN_STEPS,
        default=None,
        help=(
            "Bypass cache for this step and all following pipeline stages. "
            "Example: --from match reruns shot-match, agent_review, assemble, and render "
            "while still reusing script/VLM/TTS/Whisper/ledger cache."
        ),
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()
    footage_root, notes_path_resolved = resolve_bundled_project(args.source)
    run_dir = resolve_run_directory(
        cache_dir_arg=args.cache_dir,
        source_dir=footage_root,
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    paths = PathUtil(run_dir)
    rerun_from: PipelineStep | None = args.rerun_from
    break_after: PipelineStep | None = args.break_after
    if rerun_from is not None:
        print(f"Bypassing cache from step '{rerun_from.value}' onward.")

    print(f"\nFootage source: {footage_root}")
    print(f"Notes file: {notes_path_resolved}")

    notes_text = notes_path_resolved.read_text(encoding="utf-8")
    parsed_notes = parse_review_notes(notes_text)

    # Analyze footage
    analysis = TwelveLabsVideoAnalysisBackend(paths=paths).analyze(
        footage_root,
        parsed_notes,
        should_use_cache(step=PipelineStep.VLM, rerun_from=rerun_from),
    )

    if break_after == PipelineStep.VLM:
        print("Stopping after VLM (--break vlm).")
        return 0

    # Create script from notes
    hook_text, narration_script = LitellmScriptGenerator(paths=paths).generate(
        notes_text,
        use_cache=should_use_cache(step=PipelineStep.SCRIPT, rerun_from=rerun_from),
    )

    if break_after == PipelineStep.SCRIPT:
        print("Stopping after script (--break script).")
        return 0

    # Generate voiceover
    voice_path = ElevenLabsTts(paths=paths).synthesize(
        narration_script,
        use_cache=should_use_cache(step=PipelineStep.TTS, rerun_from=rerun_from),
    )
    voice_duration = probe_media(voice_path).get("durationSec")
    if voice_duration is None:
        raise RuntimeError(f"Unable to determine voiceover duration for {voice_path}")

    if break_after == PipelineStep.TTS:
        print("Stopping after TTS (--break tts).")
        return 0

    # Transcribe voiceover
    words = FasterWhisperWordTranscriber(paths=paths).transcribe_words(
        use_cache=should_use_cache(step=PipelineStep.WHISPER, rerun_from=rerun_from),
    )
    # Build sentences
    ledger = build_sentence_ledger(
        words,
        float(voice_duration),
        paths,
        use_cache=should_use_cache(step=PipelineStep.SENTENCE_LEDGER, rerun_from=rerun_from),
    )

    # Generate shot match
    shot_match = LitellmShotMatchOrchestrator(paths).generate_shot_match(
        analysis=analysis,
        ledger=ledger,
        use_cache=should_use_cache(step=PipelineStep.MATCH, rerun_from=rerun_from),
    )

    if break_after == PipelineStep.MATCH:
        print("Stopping after shot match (--break match).")
        return 0

    audio_duration_sec = max(float(voice_duration), 0.01)
    shot_match = LitellmAgentReviewOrchestrator(paths).refine_shot_match(
        shot_match=shot_match,
        analysis=analysis,
        ledger=ledger,
        words=words,
        voiceover_static_path=str(voice_path.resolve()),
        audio_duration_sec=audio_duration_sec,
        hook_text=hook_text or "",
        use_cache=should_use_cache(step=PipelineStep.AGENT_REVIEW, rerun_from=rerun_from),
    )

    if break_after == PipelineStep.AGENT_REVIEW:
        print("Stopping after agent_review (--break agent_review).")
        return 0

    resolved_sentences = build_resolved_sentences(
        shot_match=shot_match,
        analysis=analysis,
        sentence_ledger=ledger,
        audio_duration_sec=audio_duration_sec,
    )

    render_plan = assemble_render_plan(
        resolved_sentences=resolved_sentences,
        whisper_words=words,
        voiceover_static_path=str(voice_path.resolve()),
        audio_duration_sec=audio_duration_sec,
        run_id=analysis.run_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        hook_text=hook_text or "",
        paths=paths,
    )

    if break_after == PipelineStep.ASSEMBLE:
        print("Stopping after assemble (--break assemble); skipping Remotion render.")
        return 0

    run_remotion_render(render_plan, paths)

    print("\nPipeline complete.")
    print(f"Run directory: {paths.run_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
    except (RuntimeError, ValidationError) as error:
        print(f"\nError: {error}", file=sys.stderr)
        raise SystemExit(1)
