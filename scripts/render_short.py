#!/usr/bin/env python3
"""Orchestrate VLM analysis, narration (script/TTS/whisper), shot-match, assembly, Remotion."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from edit import LitellmShotMatchOrchestrator, assemble_render_plan
from narrative import ElevenLabsTts, FasterWhisperWordTranscriber, LitellmScriptGenerator, build_sentence_ledger
from pydantic import ValidationError
from project_inputs import PROJECT_ROOT, resolve_project_path, resolve_run_directory
from util import PathUtil, resolve_bundled_project
from vlm import TwelveLabsVideoAnalysisBackend

PUBLIC_DIR = PROJECT_ROOT / "remotion" / "public"
STATIC_PREFIX = "static:"


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
        "--run-dir",
        type=Path,
        default=None,
        help=(
            "Exact run folder for artifacts. If omitted (and without --resume), a new UUID directory "
            "is created under --cache-dir."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("cache"),
        help="Base directory scanned by --resume and used for new UUID runs (default: cache/).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Use the most recently modified subdirectory of --cache-dir as the run directory "
            "(conflicts with --run-dir)."
        ),
    )
    parser.add_argument(
        "--guidance",
        default="Cohesive TikTok restaurant b-roll pacing.",
        help="Creative hint passed to shot-match LLM.",
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
    parser.add_argument(
        "--render-output",
        type=Path,
        help="Destination MP4 path. Defaults to <run-dir>/render.mp4.",
    )
    return parser.parse_args()


def run_render_command(command: list[str]) -> None:
    print(f"\n==> Remotion render\n{' '.join(command)}")
    proc = subprocess.run(command, cwd=str(PROJECT_ROOT), check=False, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"render failed with exit code {proc.returncode}")


def local_source_path(raw: str) -> Path | None:
    if raw.startswith((STATIC_PREFIX, "http://", "https://")):
        return None
    if raw.startswith("file://"):
        from urllib.parse import unquote, urlparse

        return Path(unquote(urlparse(raw).path)).expanduser().resolve()
    return Path(raw).expanduser().resolve()


def copy_plan_media_to_public(plan: dict[str, Any]) -> Path:
    """Rewrite voice + beat sourcePath to static:* under public."""
    import uuid

    asset_dir = PUBLIC_DIR / "render-assets" / uuid.uuid4().hex
    asset_dir.mkdir(parents=True, exist_ok=False)

    static_map: dict[str, str] = {}

    def rewrite(path_str: str | None) -> str | None:
        if not path_str or not isinstance(path_str, str):
            return path_str
        p = local_source_path(path_str)
        if p is None:
            return path_str
        if not p.is_file():
            raise RuntimeError(f"Missing media file: {p}")
        resolved = p.resolve()
        key = str(resolved)
        if key not in static_map:
            dst = asset_dir / f"{len(static_map):03d}-{resolved.name}"
            shutil.copy2(resolved, dst)
            rel = dst.relative_to(PUBLIC_DIR).as_posix()
            static_map[key] = f"{STATIC_PREFIX}{rel}"
        return static_map[key]

    voice = plan.get("voiceoverStaticPath")
    if isinstance(voice, str):
        clean = voice[len(STATIC_PREFIX) :] if voice.startswith(STATIC_PREFIX) else voice
        new_voice = rewrite(clean)
        if new_voice:
            plan["voiceoverStaticPath"] = new_voice

    for beat in plan.get("beats") or []:
        if isinstance(beat, dict) and isinstance(beat.get("sourcePath"), str):
            beat["sourcePath"] = rewrite(beat["sourcePath"])

    return asset_dir


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()
    run_dir = resolve_run_directory(
        run_dir_arg=args.run_dir,
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

    if args.break_after == "tts":
        print("Stopping after TTS (--break tts).")
        return 0

    # Transcribe voiceover
    words = FasterWhisperWordTranscriber(paths=paths).transcribe_words()
    # Build sentences
    ledger = build_sentence_ledger(words, paths)

    # Generate shot match
    shot_match = LitellmShotMatchOrchestrator(paths).generate_shot_match(
        analysis=analysis,
        ledger=ledger,
        guidance=args.guidance,
    )

    if args.break_after == "match":
        print("Stopping after shot match (--break match).")
        return 0

    audio_end = max((w.end_sec for w in words), default=0.0)

    render_plan = assemble_render_plan(
        shot_match=shot_match,
        analysis=analysis,
        sentence_ledger=ledger,
        whisper_words=words,
        voiceover_static_path=str(voice_path.resolve()),
        audio_duration_sec=max(audio_end, 0.01),
        run_id=analysis.run_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    plan_path = paths.render_plan_json()
    plan_dump = render_plan.model_dump(by_alias=True)
    plan_path.write_text(json.dumps(plan_dump, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote render plan: {plan_path}")

    if args.break_after == "assemble":
        print("Stopping after assemble (--break assemble); skipping Remotion render.")
        return 0

    props = plan_dump
    asset_dir = copy_plan_media_to_public(props)
    try:
        mp4 = resolve_project_path(args.render_output) if args.render_output else paths.default_render_mp4()
        run_render_command(
            [
                "npm",
                "run",
                "render",
                "--",
                str(mp4),
                "--public-dir",
                str(PUBLIC_DIR),
                "--props",
                json.dumps(props, ensure_ascii=False),
            ]
        )
    finally:
        shutil.rmtree(asset_dir, ignore_errors=True)

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
