#!/usr/bin/env python3
"""Orchestrate VLM analysis, narration (script/TTS/whisper), shot-match, assembly, Remotion."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from edit import LitellmShotMatchOrchestrator
from edit.assemble import assemble_render_plan, build_resolved_sentences
from narrative import ElevenLabsTts, FasterWhisperWordTranscriber, LitellmScriptGenerator, build_sentence_ledger
from pydantic import ValidationError
from project_inputs import PROJECT_ROOT, resolve_run_directory
from util import PathUtil, resolve_bundled_project
from util.render import run_remotion_render
from vlm import TwelveLabsVideoAnalysisBackend
from vlm.media import probe_media


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
            "Bundled **project folder**: videos for VLM plus **notes.txt** (exact filename) "
            "in that same directory."
        ),
    )
    parser.add_argument(
        "--run-id",
        default=None,
        metavar="ID",
        help=(
            "Run folder name under --cache-dir (YYYYMMDD-HHMMSS or with -## suffix). "
            "If omitted (and without --resume), a new timestamp directory is created."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("cache"),
        help="Base directory scanned by --resume and used for new timestamp runs (default: cache/).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Use the most recently modified subdirectory of --cache-dir as the run directory "
            "(conflicts with --run-id)."
        ),
    )
    parser.add_argument(
        "--break",
        dest="break_after",
        metavar="STEP",
        choices=("script", "vlm", "tts", "match", "assemble"),
        default=None,
        help=(
            "Exit successfully right after this pipeline step. "
            "Steps: script (after script.txt), vlm (after VLM analysis), "
            "tts (after voice synthesize only; Whisper and later skipped on this run), "
            "match (after shot-match.json), assemble (after render-plan.json; Remotion render skipped)."
        ),
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()
    run_dir = resolve_run_directory(
        run_id=args.run_id,
        resume=args.resume,
        cache_dir_arg=args.cache_dir,
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    paths = PathUtil(run_dir)

    footage_root, notes_path_resolved = resolve_bundled_project(args.source)

    print(f"\nFootage source: {footage_root}")
    print(f"Notes file: {notes_path_resolved}")

    # Create script from notes
    script_text = LitellmScriptGenerator(paths=paths).generate(notes_path_resolved.read_text())

    if args.break_after == "script":
        print("Stopping after script (--break script).")
        return 0

    # Analyze footage
    analysis = TwelveLabsVideoAnalysisBackend(paths=paths).analyze(footage_root)

    if args.break_after == "vlm":
        print("Stopping after VLM (--break vlm).")
        return 0

    # Generate voiceover
    voice_path = ElevenLabsTts(paths=paths).synthesize(script_text)
    voice_duration = probe_media(voice_path).get("durationSec")
    if voice_duration is None:
        raise RuntimeError(f"Unable to determine voiceover duration for {voice_path}")

    if args.break_after == "tts":
        print("Stopping after TTS (--break tts).")
        return 0

    # Transcribe voiceover
    words = FasterWhisperWordTranscriber(paths=paths).transcribe_words()
    # Build sentences
    ledger = build_sentence_ledger(words, float(voice_duration), paths)

    # Generate shot match
    shot_match = LitellmShotMatchOrchestrator(paths).generate_shot_match(
        analysis=analysis,
        ledger=ledger,
    )

    if args.break_after == "match":
        print("Stopping after shot match (--break match).")
        return 0

    audio_duration_sec = max(float(voice_duration), 0.01)
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
        paths=paths,
    )

    if args.break_after == "assemble":
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
