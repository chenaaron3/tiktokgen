"""Analyze local videos with TwelveLabs and write generic VLM JSON output."""

from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from project_inputs import resolve_run_directory
from .media import discover_videos, extend_video_below_minimum_twelvelabs_duration, probe_media
from .notes import ParsedReviewNotes
from .schema import Clip, Provider, VlmAnalysis
from .twelvelabs import (
    DEFAULT_ANALYSIS_MODEL_NAME,
    MAX_SEGMENT_DURATION_SEC,
    MIN_SEGMENT_DURATION_SEC,
    TwelveLabsVideoAnalyzer,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIN_TWELVELABS_VIDEO_DURATION_SEC = 4.0

# Concurrent video workers in ``run()`` (TwelveLabs API batch); fixed default for programmatic use.
MAX_PARALLEL_VIDEO_ANALYSES = 10
_STAGE_DIR_PATTERN = re.compile(r"^\d+_.+")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze videos with TwelveLabs: SOURCE is a folder or one video file.",
        epilog=(
            "Examples:\n"
            "  %(prog)s ./footage\n"
            "  %(prog)s ./clip.mov\n"
            "  %(prog)s ./clip.mov --cache-dir ./cache\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Directory of videos or path to one video file.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("cache"),
        help="Base directory for run outputs. Files are written to <cache-dir>/<run-timestamp>/.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Exact output directory for this run. Overrides --cache-dir and timestamp directory creation.",
    )
    parser.add_argument(
        "--min-segment-duration",
        type=float,
        default=MIN_SEGMENT_DURATION_SEC,
        help="Minimum segment duration requested from TwelveLabs (must fit video length constraints).",
    )
    parser.add_argument(
        "--max-segment-duration",
        type=float,
        default=MAX_SEGMENT_DURATION_SEC,
        help="Maximum segment duration requested from TwelveLabs.",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=MAX_PARALLEL_VIDEO_ANALYSES,
        help="Maximum number of videos to process concurrently. Hard-capped at 10.",
    )
    return parser


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def create_analyzer(args: argparse.Namespace) -> TwelveLabsVideoAnalyzer:
    return TwelveLabsVideoAnalyzer(
        min_segment_duration=args.min_segment_duration,
        max_segment_duration=args.max_segment_duration,
    )


def analyze_video_worker(
    *,
    video_path: Path,
    args: argparse.Namespace,
) -> tuple[Clip, dict[str, Any]]:
    original = video_path
    media = probe_media(original)
    unlink_temp: Path | None = None
    try:
        upload_path, unlink_temp = extend_video_below_minimum_twelvelabs_duration(
            original,
            minimum_sec=args.min_twelvelabs_upload_sec,
        )
        if unlink_temp is not None:
            d = media.get("durationSec")
            dur_note = f"{d:.2f}s" if d is not None else "unknown duration"
            print(
                f"[{original.name}] {dur_note} below TwelveLabs minimum "
                f"({args.min_twelvelabs_upload_sec:.1f}s); extended with freeze-frame tail for upload."
            )
        analyzer = create_analyzer(args)
        return analyzer.analyze_video(
            upload_path,
            clip_source_path=original,
            clip_media=media,
            additional_context=args.additional_context,
        )
    finally:
        if unlink_temp is not None:
            unlink_temp.unlink(missing_ok=True)


def run(
    *,
    source: Path,
    cache_dir: Path = Path("cache"),
    output_dir: Path | None = None,
    min_segment_duration: float = MIN_SEGMENT_DURATION_SEC,
    max_segment_duration: float = MAX_SEGMENT_DURATION_SEC,
    max_concurrency: int = MAX_PARALLEL_VIDEO_ANALYSES,
    additional_context: ParsedReviewNotes | None = None,
) -> Path:
    """Analyze videos and return the run output directory."""
    load_dotenv(PROJECT_ROOT / ".env")

    args = argparse.Namespace(
        model=DEFAULT_ANALYSIS_MODEL_NAME,
        min_segment_duration=min_segment_duration,
        max_segment_duration=max_segment_duration,
        max_concurrency=max_concurrency,
        min_twelvelabs_upload_sec=MIN_TWELVELABS_VIDEO_DURATION_SEC,
        additional_context=additional_context,
    )

    source_path = source.expanduser().resolve()
    if source_path.is_file():
        videos = [source_path]
    elif source_path.is_dir():
        try:
            videos = discover_videos(source_path)
        except (FileNotFoundError, ValueError) as error:
            raise SystemExit(str(error)) from error
    else:
        raise SystemExit(f"Source must be a file or directory: {source_path}")

    if output_dir is None:
        run_root = resolve_run_directory(cache_dir_arg=cache_dir, source_dir=source_path)
        resolved_output_dir = run_root / "2_vlm"
        run_id = run_root.name
    else:
        resolved_output_dir = output_dir.expanduser()
        run_id = (
            resolved_output_dir.parent.name
            if _STAGE_DIR_PATTERN.match(resolved_output_dir.name)
            else resolved_output_dir.name
        )
    analysis_output = resolved_output_dir / "vlm-analysis.json"
    raw_output = resolved_output_dir / "raw-output.json"

    print(f"Run ID: {run_id}")
    print(f"Output directory: {resolved_output_dir}")

    if len(videos) == 1 and source_path.is_file():
        print(f"Single video: {videos[0].name}")
    else:
        print(f"Discovered {len(videos)} video(s)")
    skipped_clips: list[dict[str, Any]] = []

    max_workers = min(max(1, args.max_concurrency), 10, len(videos))
    print(f"Processing with max concurrency: {max_workers}")

    results: list[tuple[Clip, dict[str, Any]] | None] = [None] * len(videos)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(analyze_video_worker, video_path=video_path, args=args): index
            for index, video_path in enumerate(videos)
        }
        for future in as_completed(futures):
            index = futures[future]
            video_path = videos[index]
            try:
                results[index] = future.result()
                print(f"[{video_path.name}] Completed ({index + 1}/{len(videos)})")
            except Exception as error:
                print(
                    f"[{video_path.name}] Underlying analyze error: "
                    f"{type(error).__name__}: {error}",
                    file=sys.stderr,
                )
                raise RuntimeError(f"Failed to analyze {video_path}") from error

    clips: list[Clip] = []
    raw_clips = []
    for result in results:
        if result is None:
            raise RuntimeError("Missing analysis result")
        clip, raw_clip = result
        clips.append(clip)
        raw_clips.append(raw_clip)

    write_json(
        raw_output,
        {
            "runId": run_id,
            "provider": {"name": "twelvelabs", "model": args.model},
            "clips": raw_clips,
            "skippedClips": skipped_clips,
        },
    )
    print(f"Wrote raw TwelveLabs output: {raw_output}")

    analysis = VlmAnalysis(
        runId=run_id,
        analyzedAt=datetime.now(timezone.utc).isoformat(),
        provider=Provider(name="twelvelabs", model=args.model, rawResponseRef=str(raw_output)),
        clips=clips,
    )
    write_json(analysis_output, analysis.model_dump(by_alias=True))
    print(f"Wrote normalized VLM analysis: {analysis_output}")
    return resolved_output_dir


def main() -> int:
    args = build_parser().parse_args()
    run(
        source=args.source,
        cache_dir=args.cache_dir,
        output_dir=args.output_dir,
        min_segment_duration=args.min_segment_duration,
        max_segment_duration=args.max_segment_duration,
        max_concurrency=args.max_concurrency,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
