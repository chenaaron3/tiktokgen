#!/usr/bin/env python3
"""Analyze local videos with TwelveLabs and write generic VLM JSON output."""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from media_metadata import discover_videos, probe_media
from twelvelabs_analyzer import TwelveLabsVideoAnalyzer
from uuid6 import uuid7
from vlm_schema import Clip, Provider, VlmAnalysis


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIN_TWELVELABS_VIDEO_DURATION_SEC = 4.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze a directory of videos with TwelveLabs."
    )
    parser.add_argument("source", type=Path, help="Path to a local directory of videos.")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("cache"),
        help="Base directory for run outputs. Files are written to <cache-dir>/<run-uuid>/.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="When source is a directory, include videos from nested subdirectories.",
    )
    parser.add_argument("--model", default="pegasus1.5", help="TwelveLabs Pegasus model name.")
    parser.add_argument(
        "--min-segment-duration",
        type=float,
        default=2.0,
        help="Minimum segment duration requested from TwelveLabs.",
    )
    parser.add_argument(
        "--max-segment-duration",
        type=float,
        default=3.0,
        help="Maximum segment duration requested from TwelveLabs.",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=10,
        help="Maximum number of videos to process concurrently. Hard-capped at 10.",
    )
    return parser.parse_args()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def create_analyzer(args: argparse.Namespace) -> TwelveLabsVideoAnalyzer:
    return TwelveLabsVideoAnalyzer(
        model=args.model,
        min_segment_duration=args.min_segment_duration,
        max_segment_duration=args.max_segment_duration,
    )


def analyze_video_worker(
    *,
    video_path: Path,
    args: argparse.Namespace,
) -> tuple[Clip, dict[str, Any]]:
    analyzer = create_analyzer(args)
    return analyzer.analyze_video(video_path)


def filter_analyzable_videos(videos: list[Path]) -> tuple[list[Path], list[dict[str, Any]]]:
    analyzable = []
    skipped = []

    for video_path in videos:
        media = probe_media(video_path)
        duration_sec = media.get("durationSec")
        if duration_sec is not None and duration_sec < MIN_TWELVELABS_VIDEO_DURATION_SEC:
            skipped.append(
                {
                    "sourcePath": str(video_path),
                    "originalFilename": video_path.name,
                    "durationSec": duration_sec,
                    "reason": "video_duration_too_short",
                    "minimumDurationSec": MIN_TWELVELABS_VIDEO_DURATION_SEC,
                    "media": media,
                }
            )
            continue
        analyzable.append(video_path)

    return analyzable, skipped


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")

    args = parse_args()
    source_path = args.source.expanduser().resolve()
    if not source_path.is_dir():
        raise SystemExit(f"Source must be a directory: {source_path}")

    try:
        videos = discover_videos(source_path, recursive=args.recursive)
    except (FileNotFoundError, ValueError) as error:
        raise SystemExit(str(error)) from error

    run_id = str(uuid7())
    output_dir = args.cache_dir.expanduser() / run_id
    analysis_output = output_dir / "vlm-analysis.json"
    raw_output = output_dir / "raw-output.json"

    print(f"Run ID: {run_id}")
    print(f"Output directory: {output_dir}")

    print(f"Discovered {len(videos)} video(s)")
    videos, skipped_clips = filter_analyzable_videos(videos)
    for skipped_clip in skipped_clips:
        print(
            f"[{skipped_clip['originalFilename']}] Skipping: "
            f"{skipped_clip['durationSec']:.2f}s is below "
            f"{MIN_TWELVELABS_VIDEO_DURATION_SEC:.1f}s minimum"
        )
    if not videos:
        raise SystemExit("No videos meet the minimum duration for TwelveLabs analysis.")

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
        schemaVersion="0.3.0",
        runId=run_id,
        analyzedAt=datetime.now(timezone.utc).isoformat(),
        provider=Provider(name="twelvelabs", model=args.model, rawResponseRef=str(raw_output)),
        clips=clips,
    )
    write_json(analysis_output, analysis.model_dump(by_alias=True))
    print(f"Wrote normalized VLM analysis: {analysis_output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
