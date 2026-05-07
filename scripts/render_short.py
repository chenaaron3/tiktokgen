#!/usr/bin/env python3
"""Run analysis, edit planning, and Remotion rendering in one command."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import urllib.parse
import uuid
from pathlib import Path
from typing import Any

from edit import run_planner
from vlm import run_analysis


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = PROJECT_ROOT / "remotion" / "public"
STATIC_SOURCE_PREFIX = "static:"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze videos, generate an edit plan, and render a vertical short."
    )
    parser.add_argument("source", type=Path, help="Path to a local directory of videos.")
    parser.add_argument(
        "--guidance",
        required=True,
        help="One-line creative guidance for the edit plan.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("cache"),
        help="Base directory for run outputs. Defaults to cache/.",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        help=(
            "Exact run directory to use. If vlm-analysis.json or edit-plan.json already "
            "exist there, those stages are skipped."
        ),
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Include videos from nested subdirectories.",
    )
    parser.add_argument(
        "--vlm-model",
        default="pegasus1.5",
        help="TwelveLabs Pegasus model name.",
    )
    parser.add_argument(
        "--planner-model",
        help="OpenAI model for edit planning. Defaults to OPENAI_MODEL or the planner default.",
    )
    parser.add_argument(
        "--target-duration",
        type=float,
        default=35.0,
        help="Target output duration in seconds.",
    )
    parser.add_argument(
        "--min-segment-duration",
        type=float,
        default=2.0,
        help="Minimum segment duration requested from TwelveLabs.",
    )
    parser.add_argument(
        "--max-segment-duration",
        type=float,
        default=4.0,
        help="Maximum segment duration requested from TwelveLabs.",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=10,
        help="Maximum number of videos to process concurrently. Hard-capped by analyzer at 10.",
    )
    parser.add_argument(
        "--render-output",
        type=Path,
        help="Optional final MP4 output path. Defaults to <run-dir>/render.mp4.",
    )
    return parser.parse_args()


def resolve_project_path(path: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded
    return (PROJECT_ROOT / expanded).resolve()


def run_render_command(command: list[str]) -> None:
    label = "Render video"
    print(f"\n==> {label}")
    print(" ".join(command))
    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="")

    exit_code = process.wait()
    if exit_code != 0:
        raise RuntimeError(f"{label} failed with exit code {exit_code}")


def local_source_path(source_path: str) -> Path | None:
    if source_path.startswith(("http://", "https://", STATIC_SOURCE_PREFIX)):
        return None
    if source_path.startswith("file://"):
        parsed = urllib.parse.urlparse(source_path)
        return Path(urllib.parse.unquote(parsed.path)).expanduser().resolve()
    return Path(source_path).expanduser().resolve()


def copy_assets_to_public(plan: dict[str, Any]) -> Path | None:
    asset_dir: Path | None = None
    static_paths: dict[Path, str] = {}
    for segment in plan.get("segments", []):
        if not isinstance(segment, dict) or not isinstance(segment.get("sourcePath"), str):
            continue
        source_path = local_source_path(segment["sourcePath"])
        if source_path is None:
            continue
        if not source_path.exists():
            raise RuntimeError(f"Cannot render because source media file is missing: {source_path}")
        if asset_dir is None:
            asset_dir = PUBLIC_DIR / "render-assets" / uuid.uuid4().hex
            asset_dir.mkdir(parents=True, exist_ok=False)
        if source_path not in static_paths:
            public_asset_path = asset_dir / f"{len(static_paths):03d}-{source_path.name}"
            shutil.copy2(source_path, public_asset_path)
            static_paths[source_path] = (
                f"{STATIC_SOURCE_PREFIX}{public_asset_path.relative_to(PUBLIC_DIR).as_posix()}"
            )
        segment["sourcePath"] = static_paths[source_path]
    return asset_dir


def main() -> int:
    args = parse_args()
    run_dir = resolve_project_path(args.run_dir) if args.run_dir else None

    if run_dir is not None:
        analysis_path = run_dir / "vlm-analysis.json"
        edit_plan_path = run_dir / "edit-plan.json"
    else:
        analysis_path = None
        edit_plan_path = None

    if analysis_path is not None and analysis_path.exists():
        print(f"\n==> Analyze videos (cached: {analysis_path})")
    else:
        print("\n==> Analyze videos")
        run_dir = run_analysis(
            source=resolve_project_path(args.source),
            cache_dir=resolve_project_path(args.cache_dir),
            output_dir=run_dir,
            recursive=args.recursive,
            model=args.vlm_model,
            min_segment_duration=args.min_segment_duration,
            max_segment_duration=args.max_segment_duration,
            max_concurrency=args.max_concurrency,
        )
        analysis_path = run_dir / "vlm-analysis.json"
        edit_plan_path = run_dir / "edit-plan.json"

    if edit_plan_path.exists():
        print(f"\n==> Generate edit plan (cached: {edit_plan_path})")
    else:
        print("\n==> Generate edit plan")
        run_planner(
            analysis_path=analysis_path,
            guidance=args.guidance,
            output_path=edit_plan_path,
            model=args.planner_model,
            target_duration=args.target_duration,
        )

    edit_plan = json.loads(edit_plan_path.read_text())
    asset_dir = copy_assets_to_public(edit_plan)
    try:
        render_command = [
            "npm",
            "run",
            "render",
            "--",
            str(resolve_project_path(args.render_output) if args.render_output else run_dir / "render.mp4"),
            "--public-dir",
            str(PUBLIC_DIR),
            "--props",
            json.dumps(edit_plan, ensure_ascii=False),
        ]
        run_render_command(render_command)
    finally:
        if asset_dir is not None:
            shutil.rmtree(asset_dir, ignore_errors=True)

    print("\nPipeline complete")
    print(f"Run directory: {run_dir}")
    print(f"Analysis: {analysis_path}")
    print(f"Edit plan: {edit_plan_path}")
    print(f"Render: {resolve_project_path(args.render_output) if args.render_output else run_dir / 'render.mp4'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
    except RuntimeError as error:
        print(f"\nError: {error}", file=sys.stderr)
        raise SystemExit(1)
