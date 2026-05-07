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

from uuid6 import uuid7

from contracts import SentenceLedger, WordToken
from dotenv import load_dotenv
from edit import assemble_render_plan, run_shot_match
from edit.schema_shot_match import ShotMatch
from narrative import ElevenLabsTts, FasterWhisperWordTranscriber, LitellmScriptGenerator, build_sentence_ledger
from pydantic import ValidationError
from vlm import TwelveLabsVideoAnalysisBackend, VideoAnalysisBackend
from vlm.schema import VlmAnalysis

from project_inputs import resolve_bundled_project


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = PROJECT_ROOT / "remotion" / "public"
STATIC_PREFIX = "static:"


def resolve_project_path(path: Path) -> Path:
    expanded = path.expanduser()
    return expanded.resolve() if expanded.is_absolute() else (PROJECT_ROOT / expanded).resolve()


def find_latest_run_directory(cache_dir: Path) -> Path | None:
    """Return the subdirectory of `cache_dir` with the newest ``st_mtime``, or ``None`` if empty."""
    if not cache_dir.is_dir():
        return None
    candidates = [
        p for p in cache_dir.iterdir() if p.is_dir() and not p.name.startswith(".")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def resolve_run_directory(
    *,
    run_dir_arg: Path | None,
    resume: bool,
    cache_dir_arg: Path,
) -> Path:
    """Pick explicit ``--run-dir``, latest under cache (``--resume``), or ``cache-dir/<new-uuid>``."""
    if run_dir_arg is not None and resume:
        raise SystemExit("Use only one of --run-dir or --resume (not both).")
    cache_base = resolve_project_path(cache_dir_arg)
    cache_base.mkdir(parents=True, exist_ok=True)
    if run_dir_arg is not None:
        return resolve_project_path(run_dir_arg)
    if resume:
        latest = find_latest_run_directory(cache_base)
        if latest is None:
            raise SystemExit(
                f"No run directories found under {cache_base}; "
                "run without --resume to create a new UUID run folder."
            )
        print(f"Resuming latest run: {latest}")
        return latest
    new_id = str(uuid7())
    run = cache_base / new_id
    print(f"New run directory: {run}")
    return run


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
            "Footage: path to one video **or** a folder of clips for VLM. "
            "**Bundled session:** path to a directory that contains your videos "
            "**and** notes (notes.txt preferred, or exactly one non-readme *.txt)—omit --notes-file in that case."
        ),
    )
    parser.add_argument(
        "--notes-file",
        type=Path,
        help=(
            "Explicit rough notes path. Required when SOURCE is a **single video file**. "
            "Optional when SOURCE is a **directory** containing notes.txt / one story *.txt beside the clips."
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
        "--recursive",
        action="store_true",
        help="When source is a folder, recurse into nested videos.",
    )
    parser.add_argument(
        "--guidance",
        default="Cohesive TikTok restaurant b-roll pacing.",
        help="Creative hint passed to shot-match LLM.",
    )
    parser.add_argument(
        "--auto-approve-script",
        action="store_true",
        help="Copy script.draft.txt → script.txt without manual gate.",
    )
    parser.add_argument(
        "--stop-after-script",
        action="store_true",
        help="Exit after writing script draft (requires usable notes when script.txt missing).",
    )
    parser.add_argument(
        "--stop-after-shot-match",
        action="store_true",
        help="Exit after shot-match.json (assembly/render skipped).",
    )
    parser.add_argument(
        "--assemble-only",
        action="store_true",
        help="Reuse existing artifacts; run assembly (+ optional render) only.",
    )
    parser.add_argument("--vlm-model", default="pegasus1.5", help="TwelveLabs Pegasus model.")
    parser.add_argument("--shot-match-model", help="LiteLLM model override for shot matching.")
    parser.add_argument(
        "--skip-render",
        action="store_true",
        help="Stop after writing render-plan.json (still runs asset prep if needed).",
    )
    parser.add_argument(
        "--render-output",
        type=Path,
        help="Destination MP4 path. Defaults to <run-dir>/render.mp4.",
    )
    parser.add_argument(
        "--faster-whisper-model",
        default="base.en",
        help="Model id for faster-whisper transcription.",
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


def stage_script(*, run_dir: Path, notes_file: Path | None, auto_approve: bool, stop_after: bool) -> None:
    draft = run_dir / "script.draft.txt"
    approved = run_dir / "script.txt"
    if approved.is_file():
        return
    if notes_file is None or not notes_file.is_file():
        raise SystemExit(f"Need {approved} or valid --notes-file to create a script draft.")
    notes = notes_file.read_text()
    obs_file = run_dir / "llm-observability" / "script.json"
    obs_file.parent.mkdir(parents=True, exist_ok=True)
    generator = LitellmScriptGenerator(observability_path=obs_file)
    text = generator.generate(notes)
    draft.write_text(text.strip() + "\n")
    print(f"Wrote script draft: {draft}")
    if auto_approve:
        shutil.copy(draft, approved)
        print(f"Auto-approved → {approved}")
    else:
        print("Copy or rename script.draft.txt → script.txt before continuing.")
    if stop_after or not approved.is_file():
        raise SystemExit(0)


def load_json_model(path: Path, model: type[ShotMatch] | type[VlmAnalysis]) -> Any:
    raw = json.loads(path.read_text())
    return model.model_validate(raw)


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()
    run_dir = resolve_run_directory(
        run_dir_arg=args.run_dir,
        resume=args.resume,
        cache_dir_arg=args.cache_dir,
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    raw_target = resolve_project_path(args.source)

    if args.notes_file is not None:
        footage_root = raw_target
        notes_path_resolved = resolve_project_path(args.notes_file)
    else:
        if raw_target.is_file():
            raise SystemExit(
                "When SOURCE is a single video file you must pass --notes-file PATH. "
                "Or point SOURCE at a **folder** that contains both your clips and notes.txt "
                "(or exactly one notes .txt)—for example assets/05-03."
            )
        footage_root, notes_path_resolved = resolve_bundled_project(
            raw_target, recursive=args.recursive
        )

    print(f"\nFootage source: {footage_root}")
    print(f"Notes file: {notes_path_resolved}")

    if not args.assemble_only:
        try:
            stage_script(
                run_dir=run_dir,
                notes_file=notes_path_resolved,
                auto_approve=args.auto_approve_script,
                stop_after=args.stop_after_script,
            )
        except SystemExit as exited:
            if isinstance(exited.code, int):
                return exited.code
            if exited.code is None:
                return 0
            return 1

    script_path = run_dir / "script.txt"
    if not script_path.is_file():
        raise SystemExit(f"Missing approved script: {script_path}")

    vlm_path = run_dir / "vlm-analysis.json"
    analysis: VlmAnalysis | None = None
    if not vlm_path.is_file():
        backend: VideoAnalysisBackend = TwelveLabsVideoAnalysisBackend()
        print("\n==> VLM analyze")
        out_dir = backend.analyze(
            source=footage_root,
            cache_dir=run_dir.parent,
            output_dir=run_dir,
            recursive=args.recursive,
            model=args.vlm_model,
            min_segment_duration=2.0,
            max_segment_duration=4.0,
            max_concurrency=10,
        )
        analysis = load_json_model(out_dir / "vlm-analysis.json", VlmAnalysis)
    else:
        analysis = load_json_model(vlm_path, VlmAnalysis)

    voice_path = run_dir / "voiceover.mp3"
    if not voice_path.is_file():
        print("\n==> ElevenLabs TTS")
        ElevenLabsTts().synthesize(script_path.read_text(), voice_path)

    whisper_path = run_dir / "whisper-words.json"
    words: list[WordToken]
    if whisper_path.is_file():
        raw = json.loads(whisper_path.read_text())
        words = [WordToken.model_validate(w) for w in raw.get("words", [])]
    else:
        print("\n==> faster-whisper")
        transcriber = FasterWhisperWordTranscriber(model_size=args.faster_whisper_model)
        words = transcriber.transcribe_words(voice_path)
        whisper_path.write_text(
            json.dumps({"words": [w.model_dump(by_alias=True) for w in words]}, indent=2) + "\n"
        )

    ledger = build_sentence_ledger(words)
    ledger_path = run_dir / "sentence-ledger.json"
    ledger_path.write_text(json.dumps(ledger.model_dump(by_alias=True), indent=2) + "\n")

    shot_path = run_dir / "shot-match.json"
    observability = run_dir / "llm-observability" / "shot-match.json"
    if shot_path.is_file():
        shot_match = load_json_model(shot_path, ShotMatch)
        print(f"\n==> shot-match (cached: {shot_path})")
    else:
        print("\n==> Shot-match LLM")
        observability.parent.mkdir(parents=True, exist_ok=True)
        shot_match = run_shot_match(
            analysis=analysis,
            ledger=ledger,
            guidance=args.guidance,
            model=args.shot_match_model,
            observability_path=observability,
        )
        shot_path.write_text(
            json.dumps(shot_match.model_dump(by_alias=True), indent=2, ensure_ascii=False) + "\n"
        )

    if args.stop_after_shot_match:
        print("Stopping after shot-match per flag.")
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
        hook_text=script_path.read_text().splitlines()[0][:120] if script_path.is_file() else None,
    )

    plan_path = run_dir / "render-plan.json"
    plan_dump = render_plan.model_dump(by_alias=True)
    plan_path.write_text(json.dumps(plan_dump, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote render plan: {plan_path}")

    if args.skip_render:
        return 0

    props = plan_dump
    asset_dir = copy_plan_media_to_public(props)
    try:
        mp4 = resolve_project_path(args.render_output) if args.render_output else run_dir / "render.mp4"
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
    print(f"Run directory: {run_dir}")
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
