#!/usr/bin/env python3
"""Generate a minimal Remotion edit plan from VLM analysis JSON."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import litellm
from dotenv import load_dotenv
from pydantic import ValidationError

from logger import install_local_observability_logger
from vlm.schema import Clip, VlmAnalysis

from .schema import EditPlan


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = "openai/gpt-4.1-mini"
DEFAULT_OUTPUT_NAME = "edit-plan.json"
MAX_TIMELINE_REPAIR_DRIFT_SEC = 2.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Remotion edit plan from normalized VLM analysis."
    )
    parser.add_argument(
        "analysis",
        type=Path,
        help="Path to cache/<run-id>/vlm-analysis.json.",
    )
    parser.add_argument(
        "--guidance",
        required=True,
        help="One-line creative guidance, e.g. 'make this a stylish West Village afternoon'.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output edit-plan JSON path. Defaults to edit-plan.json beside the analysis file.",
    )
    parser.add_argument(
        "--model",
        help=f"LiteLLM model for planning. Defaults to OPENAI_MODEL or {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--target-duration",
        type=float,
        default=35.0,
        help="Target output duration in seconds.",
    )
    return parser.parse_args()


def read_analysis(path: Path) -> VlmAnalysis:
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise SystemExit(f"Could not read VLM analysis: {error}") from error

    try:
        return VlmAnalysis.model_validate(data)
    except ValidationError as error:
        raise SystemExit(f"Invalid VLM analysis JSON:\n{error}") from error


def location_key(clip: Clip) -> str:
    if clip.location:
        latitude = clip.location.get("latitude")
        longitude = clip.location.get("longitude")
        if isinstance(latitude, int | float) and isinstance(longitude, int | float):
            return f"{latitude:.4f},{longitude:.4f}"
    return "unknown"


def summarize_analysis(analysis: VlmAnalysis) -> dict[str, Any]:
    clips = []
    for clip in analysis.clips:
        moments = []
        for moment in clip.moments:
            moments.append(
                {
                    "momentId": moment.moment_id,
                    "startSec": moment.start_sec,
                    "endSec": moment.end_sec,
                    "description": moment.description,
                    "subjects": moment.subjects,
                    "actions": moment.actions,
                    "visibleText": moment.visible_text,
                    "spokenText": moment.spoken_text,
                    "audio": moment.audio,
                    "quality": moment.quality,
                    "issues": moment.issues,
                    "whyUseful": moment.why_useful,
                }
            )

        clips.append(
            {
                "id": clip.id,
                "sourcePath": clip.source_path,
                "originalFilename": clip.original_filename,
                "durationSec": clip.duration_sec,
                "capturedAt": clip.captured_at,
                "location": clip.location,
                "locationKey": location_key(clip),
                "media": {
                    "width": clip.media.get("width"),
                    "height": clip.media.get("height"),
                    "fps": clip.media.get("fps"),
                    "orientation": clip.media.get("orientation"),
                },
                "summary": clip.summary,
                "moments": moments,
            }
        )

    return {
        "schemaVersion": analysis.schema_version,
        "runId": analysis.run_id,
        "clipCount": len(analysis.clips),
        "clips": clips,
    }


def load_schema_for_structured_output() -> dict[str, Any]:
    schema = EditPlan.model_json_schema()
    return make_openai_strict_schema(schema)


def make_openai_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Adapt Pydantic JSON Schema to OpenAI strict structured output rules."""
    if schema.get("type") == "object" and isinstance(schema.get("properties"), dict):
        schema["required"] = list(schema["properties"].keys())
        schema["additionalProperties"] = False

    # Defaults make fields optional in JSON Schema, but OpenAI strict schemas
    # require every property to be present. Nullable fields still use null.
    schema.pop("default", None)

    for key in ("properties", "$defs"):
        nested = schema.get(key)
        if isinstance(nested, dict):
            for value in nested.values():
                if isinstance(value, dict):
                    make_openai_strict_schema(value)

    for key in ("items", "anyOf", "oneOf", "allOf"):
        nested = schema.get(key)
        if isinstance(nested, dict):
            make_openai_strict_schema(nested)
        elif isinstance(nested, list):
            for value in nested:
                if isinstance(value, dict):
                    make_openai_strict_schema(value)

    return schema


def create_chat_completion(
    *,
    model: str,
    messages: list[dict[str, str]],
    response_format: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    if metadata is not None:
        kwargs["metadata"] = metadata

    response = litellm.completion(**kwargs)
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("LiteLLM returned an empty response")
    return content


def as_number(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None


def normalize_edit_plan_data(data: dict[str, Any]) -> dict[str, Any]:
    """Repair small timeline-boundary drift in structured LLM output."""
    segments = data.get("segments")
    if not isinstance(segments, list):
        return data

    segment_by_id = {
        segment.get("id"): segment
        for segment in segments
        if isinstance(segment, dict) and isinstance(segment.get("id"), str)
    }
    locations = data.get("locations")
    text_overlays = data.get("text")
    timeline_items = [
        *segments,
        *(locations if isinstance(locations, list) else []),
        *(text_overlays if isinstance(text_overlays, list) else []),
    ]
    timeline_ends = [
        end
        for item in timeline_items
        if isinstance(item, dict)
        for end in [as_number(item.get("timelineEndSec"))]
        if end is not None
    ]

    duration_sec = as_number(data.get("durationSec"))
    if duration_sec is not None and timeline_ends:
        max_timeline_end = max(timeline_ends)
        drift_sec = max_timeline_end - duration_sec
        if 0 < drift_sec <= MAX_TIMELINE_REPAIR_DRIFT_SEC:
            data["durationSec"] = round(max_timeline_end, 3)

    if isinstance(locations, list):
        for location in locations:
            if not isinstance(location, dict) or not isinstance(location.get("segmentIds"), list):
                continue
            referenced_segments = [
                segment_by_id[segment_id]
                for segment_id in location["segmentIds"]
                if segment_id in segment_by_id
            ]
            starts = [
                start
                for segment in referenced_segments
                for start in [as_number(segment.get("timelineStartSec"))]
                if start is not None
            ]
            ends = [
                end
                for segment in referenced_segments
                for end in [as_number(segment.get("timelineEndSec"))]
                if end is not None
            ]
            if starts and ends:
                location["timelineStartSec"] = round(min(starts), 3)
                location["timelineEndSec"] = round(max(ends), 3)

    return data


def generate_outline(
    *,
    model: str,
    guidance: str,
    target_duration: float,
    analysis_summary: dict[str, Any],
    observability_path: Path,
) -> str:
    system_prompt = (
        "You are a short-form food/travel video editor. Create a concise editing strategy "
        "before the final JSON plan. Think in this hierarchy: H1 theme, H2 locations, "
        "H3 supporting clips. Prioritize a scroll-stopping first 1-3 seconds, coherent "
        "location sections, visual variety, and simple minimal text overlays."
    )
    user_prompt = {
        "guidance": guidance,
        "targetDurationSec": target_duration,
        "analysis": analysis_summary,
        "instructions": [
            "Return concise plain text only.",
            "Name the H1 theme and hook text.",
            "List the location sections in the order they should appear.",
            "List the strongest candidate moments and why they flow.",
            "Call out weak/repetitive footage to avoid.",
        ],
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},
    ]
    content = create_chat_completion(
        model=model,
        messages=messages,
        metadata={
            "stage": "outline",
            "observabilityPath": str(observability_path),
        },
    )
    return content


def generate_plan(
    *,
    model: str,
    guidance: str,
    target_duration: float,
    analysis_path: Path,
    analysis_summary: dict[str, Any],
    outline: str,
    observability_path: Path,
) -> EditPlan:
    schema = load_schema_for_structured_output()
    now = datetime.now(timezone.utc).isoformat()
    system_prompt = (
        "You generate strict JSON edit plans for a Remotion renderer. The output is a "
        "minimal TikTok-style food/travel short plan. Do not include voiceover, music, "
        "captions, platform, format, or style metadata. The edit must have a coherent "
        "H1 theme, H2 location sections, and flat H3 segments linked by locationId."
    )
    user_prompt = {
        "guidance": guidance,
        "targetDurationSec": target_duration,
        "createdAt": now,
        "sourceAnalysisRef": str(analysis_path),
        "analysis": analysis_summary,
        "outline": outline,
        "rules": [
            "Use schemaVersion 0.1.0.",
            "durationSec should be close to targetDurationSec, but may be shorter if footage is limited.",
            "The first segment must be the strongest visual hook and have role hook.",
            "Segment role must be one of: hook, setup, context, signature, detail, texture, ambience, transition, payoff, ending.",
            "Prefer great/good moments; use okay only for important context; avoid poor.",
            "Use 1-3 second segments by default; holds over 3 seconds must be exceptional.",
            "Locations are H2 sections derived from location metadata when possible.",
            "Segments are flat H3 timeline clips and must reference a locationId.",
            "Every segment reason must explain how it supports the theme and parent location.",
            "Avoid more than two adjacent segments with the same visualType or subject.",
            "Text overlays must be sparse, short, and grounded in VLM/user context.",
            "Set crop to x/y/scale values for vertical cover framing; use x=0.5 y=0.5 scale=1.0 when unsure.",
            "Record assumptions when location labels or story details are inferred.",
        ],
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},
    ]
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "edit_plan",
            "schema": schema,
            "strict": True,
        },
    }
    content = create_chat_completion(
        model=model,
        messages=messages,
        response_format=response_format,
        metadata={
            "stage": "edit_plan",
            "observabilityPath": str(observability_path),
        },
    )
    try:
        data = json.loads(content)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"LiteLLM returned invalid JSON: {error}\n{content}") from error
    print("Validated edit plan JSON parse")
    data = normalize_edit_plan_data(data)

    try:
        plan = EditPlan.model_validate(data)
    except ValidationError as error:
        raise RuntimeError(f"LiteLLM returned an invalid edit plan:\n{error}") from error
    print("Validated edit plan schema")
    return plan


def validate_against_source(plan: EditPlan, analysis: VlmAnalysis) -> None:
    clips = {clip.id: clip for clip in analysis.clips}
    errors = []
    for segment in plan.segments:
        clip = clips.get(segment.clip_id)
        if clip is None:
            errors.append(f"{segment.id} references missing clipId {segment.clip_id}")
            continue
        if segment.source_path != clip.source_path:
            errors.append(f"{segment.id} sourcePath does not match clip {segment.clip_id}")
        if clip.duration_sec is not None and segment.source_end_sec > clip.duration_sec + 0.01:
            errors.append(
                f"{segment.id} sourceEndSec {segment.source_end_sec} exceeds "
                f"{segment.clip_id} duration {clip.duration_sec}"
            )
    if errors:
        raise RuntimeError("Edit plan failed source validation:\n" + "\n".join(f"- {error}" for error in errors))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def run(
    *,
    analysis_path: Path,
    guidance: str,
    output_path: Path | None = None,
    model: str | None = None,
    target_duration: float = 35.0,
) -> Path:
    """Generate an edit plan and return its output path."""
    load_dotenv(PROJECT_ROOT / ".env")

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required in the environment or .env")

    resolved_analysis_path = analysis_path.expanduser().resolve()
    resolved_output_path = (
        output_path.expanduser().resolve()
        if output_path is not None
        else resolved_analysis_path.parent / DEFAULT_OUTPUT_NAME
    )
    planning_model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    observability_dir = resolved_output_path.parent / "llm-observability"
    outline_observability_path = observability_dir / "01-outline.json"
    plan_observability_path = observability_dir / "02-edit-plan.json"
    analysis = read_analysis(resolved_analysis_path)
    analysis_summary = summarize_analysis(analysis)
    install_local_observability_logger()

    print("Planning story outline...")
    outline = generate_outline(
        model=planning_model,
        guidance=guidance,
        target_duration=target_duration,
        analysis_summary=analysis_summary,
        observability_path=outline_observability_path,
    )

    print("Generating edit plan...")
    plan = generate_plan(
        model=planning_model,
        guidance=guidance,
        target_duration=target_duration,
        analysis_path=resolved_analysis_path,
        analysis_summary=analysis_summary,
        outline=outline,
        observability_path=plan_observability_path,
    )
    validate_against_source(plan, analysis)
    print("Validated edit plan source references")

    write_json(resolved_output_path, plan.model_dump(by_alias=True))
    outline_path = resolved_output_path.with_name("edit-outline.txt")
    outline_path.write_text(outline.strip() + "\n")
    print(f"Wrote edit plan: {resolved_output_path}")
    print(f"Wrote planning outline: {outline_path}")
    print(f"Wrote LLM observability: {observability_dir}")
    return resolved_output_path


def main() -> int:
    args = parse_args()
    run(
        analysis_path=args.analysis,
        guidance=args.guidance,
        output_path=args.output,
        model=args.model,
        target_duration=args.target_duration,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
