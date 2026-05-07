#!/usr/bin/env python3
"""Batch-transcribe local videos with OpenAI whisper-1 (parallel uploads)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import APIStatusError, OpenAI, RateLimitError

from vlm.media import discover_videos

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OPENAI_MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transcribe videos in a directory using OpenAI whisper-1.",
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Video file or directory containing videos.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to write transcript files (<stem>.txt by default).",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="When source is a directory, include nested videos.",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=6,
        help="Maximum concurrent API requests (default: 6).",
    )
    parser.add_argument(
        "--model",
        default="whisper-1",
        help="Transcription model name (default: whisper-1).",
    )
    parser.add_argument(
        "--response-format",
        choices=("json", "text", "srt", "verbose_json", "vtt"),
        default="text",
        help=(
            "API response format (default: text). Writes <stem>.txt for text; "
            "<stem>.json for json/verbose_json; .srt / .vtt for those formats."
        ),
    )
    parser.add_argument(
        "--language",
        help="Optional BCP-47 language hint (e.g. en).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-transcribe even if the output file already exists.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=5,
        help="Max retries per file on rate limits (default: 5).",
    )
    parser.add_argument(
        "--no-manifest",
        action="store_true",
        help=(
            "Do not write transcription-manifest.json / .jsonl "
            "(source path, transcript path, stem, status)."
        ),
    )
    return parser.parse_args()


def resolve_project_path(path: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (PROJECT_ROOT / expanded).resolve()


def transcription_to_dict(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return obj
    return {"text": getattr(obj, "text", str(obj))}


def output_path_for(video_path: Path, output_dir: Path, response_format: str) -> Path:
    stem = video_path.stem
    if response_format in ("json", "verbose_json"):
        return output_dir / f"{stem}.json"
    if response_format == "srt":
        return output_dir / f"{stem}.srt"
    if response_format == "vtt":
        return output_dir / f"{stem}.vtt"
    return output_dir / f"{stem}.txt"


def transcription_file_body(result: Any, response_format: str) -> str:
    """String to write to disk (plain transcript for text; raw srt/vtt for those)."""
    text = getattr(result, "text", None)
    if text is not None:
        return text
    if isinstance(result, str):
        return result
    return str(result)


def write_transcription_output(
    *,
    out_path: Path,
    result: Any,
    response_format: str,
    video_path: Path,
    model: str,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if response_format in ("json", "verbose_json"):
        payload = {
            "sourcePath": str(video_path),
            "sourceFilename": video_path.name,
            "model": model,
            "responseFormat": response_format,
            "transcription": transcription_to_dict(result),
        }
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    else:
        body = transcription_file_body(result, response_format)
        if body and not body.endswith("\n"):
            body += "\n"
        out_path.write_text(body, encoding="utf-8")


def ensure_uploadable_audio(video_path: Path) -> Path:
    """Return a path OpenAI can accept (<=25 MB). Re-encode with ffmpeg when needed."""
    size = video_path.stat().st_size
    if size <= OPENAI_MAX_UPLOAD_BYTES:
        return video_path

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError(
            f"{video_path.name} is {size / 1e6:.1f} MB (limit 25 MB) and ffmpeg was not "
            "found in PATH. Install ffmpeg or shrink the file before transcribing."
        )

    fd, tmp_name = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    tmp_path = Path(tmp_name)

    def run_encode(bitrate: str) -> None:
        cmd = [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "libmp3lame",
            "-b:a",
            bitrate,
            str(tmp_path),
        ]
        subprocess.run(cmd, check=True)

    try:
        for bitrate in ("64k", "48k", "32k"):
            run_encode(bitrate)
            if tmp_path.stat().st_size <= OPENAI_MAX_UPLOAD_BYTES:
                return tmp_path
        raise RuntimeError(
            f"After re-encoding, audio for {video_path.name} is still over 25 MB. "
            "Split the source or use a lower-level pipeline."
        )
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def transcribe_one(
    *,
    client: OpenAI,
    video_path: Path,
    out_path: Path,
    model: str,
    response_format: str,
    language: str | None,
    max_retries: int,
) -> dict[str, Any]:
    audio_path = ensure_uploadable_audio(video_path)
    try:
        kwargs: dict[str, Any] = {
            "model": model,
            "response_format": response_format,
        }
        if language:
            kwargs["language"] = language

        delay = 2.0
        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                with audio_path.open("rb") as audio_file:
                    kwargs["file"] = audio_file
                    result = client.audio.transcriptions.create(**kwargs)
                break
            except (RateLimitError, APIStatusError) as err:
                last_error = err
                code = getattr(err, "status_code", None)
                if isinstance(err, RateLimitError) or code == 429:
                    if attempt >= max_retries:
                        raise
                    time.sleep(delay)
                    delay = min(delay * 2, 90.0)
                    continue
                raise
        else:
            assert last_error is not None
            raise last_error
    finally:
        if audio_path != video_path:
            audio_path.unlink(missing_ok=True)

    write_transcription_output(
        out_path=out_path,
        result=result,
        response_format=response_format,
        video_path=video_path,
        model=model,
    )
    return {"ok": True, "path": str(video_path), "out": str(out_path)}


def manifest_row(
    *,
    vp: Path,
    output_dir: Path,
    response_format: str,
    status: str,
    error: str | None = None,
) -> dict[str, Any]:
    out_path = output_path_for(vp, output_dir, response_format)
    row: dict[str, Any] = {
        "sourcePath": str(vp.resolve()),
        "sourceFilename": vp.name,
        "videoStem": vp.stem,
        "transcriptPath": str(out_path.resolve()),
        "transcriptFilename": out_path.name,
        "transcriptExists": out_path.exists(),
        "status": status,
    }
    if error:
        row["error"] = error
    return row


def append_manifest_jsonl(path: Path, row: dict[str, Any], lock: threading.Lock) -> None:
    line = json.dumps(row, ensure_ascii=False) + "\n"
    with lock:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def build_manifest_entries(
    *,
    videos: list[Path],
    output_dir: Path,
    response_format: str,
    per_source: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """One row per input video: links source file to transcript path and run status."""
    rows: list[dict[str, Any]] = []
    for vp in sorted(videos, key=lambda p: p.name):
        key = str(vp.resolve())
        out_path = output_path_for(vp, output_dir, response_format)
        row: dict[str, Any] = {
            "sourcePath": key,
            "sourceFilename": vp.name,
            "videoStem": vp.stem,
            "transcriptPath": str(out_path.resolve()),
            "transcriptFilename": out_path.name,
            "transcriptExists": out_path.exists(),
        }
        info = per_source.get(key)
        if info is not None:
            row["status"] = info.get("status", "unknown")
            if info.get("error"):
                row["error"] = info["error"]
        else:
            row["status"] = "unknown"
        rows.append(row)
    return rows


def worker(
    *,
    video_path: Path,
    output_dir: Path,
    client: OpenAI,
    model: str,
    response_format: str,
    language: str | None,
    force: bool,
    max_retries: int,
) -> dict[str, Any]:
    out_path = output_path_for(video_path, output_dir, response_format)
    if out_path.exists() and not force:
        return {"ok": True, "skipped": True, "path": str(video_path), "out": str(out_path)}
    return transcribe_one(
        client=client,
        video_path=video_path,
        out_path=out_path,
        model=model,
        response_format=response_format,
        language=language,
        max_retries=max_retries,
    )


def main() -> int:
    args = parse_args()
    load_dotenv(PROJECT_ROOT / ".env")

    source = resolve_project_path(args.source)
    output_dir = resolve_project_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        videos = discover_videos(source, recursive=args.recursive)
    except (FileNotFoundError, ValueError) as err:
        print(err, file=sys.stderr)
        return 1

    client = OpenAI()
    max_workers = max(1, args.max_concurrency)
    ok = 0
    skipped = 0
    failed: list[str] = []
    per_source: dict[str, dict[str, Any]] = {}
    manifest_jsonl = output_dir / "transcription-manifest.jsonl"
    manifest_lock = threading.Lock()
    if not args.no_manifest:
        manifest_jsonl.write_text("", encoding="utf-8")

    print(f"Transcribing {len(videos)} file(s) -> {output_dir} (workers={max_workers})", flush=True)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                worker,
                video_path=vp,
                output_dir=output_dir,
                client=client,
                model=args.model,
                response_format=args.response_format,
                language=args.language,
                force=args.force,
                max_retries=args.retries,
            ): vp
            for vp in videos
        }
        for future in as_completed(futures):
            vp = futures[future]
            key = str(vp.resolve())
            try:
                info = future.result()
                if info.get("skipped"):
                    skipped += 1
                    per_source[key] = {"status": "skipped"}
                    print(f"[skip] {vp.name}", flush=True)
                    if not args.no_manifest:
                        append_manifest_jsonl(
                            manifest_jsonl,
                            manifest_row(
                                vp=vp,
                                output_dir=output_dir,
                                response_format=args.response_format,
                                status="skipped",
                            ),
                            manifest_lock,
                        )
                else:
                    ok += 1
                    per_source[key] = {"status": "ok"}
                    print(f"[ok]   {vp.name}", flush=True)
                    if not args.no_manifest:
                        append_manifest_jsonl(
                            manifest_jsonl,
                            manifest_row(
                                vp=vp,
                                output_dir=output_dir,
                                response_format=args.response_format,
                                status="ok",
                            ),
                            manifest_lock,
                        )
            except Exception as err:  # noqa: BLE001 — surface any API/ffmpeg failure
                failed.append(f"{vp.name}: {err}")
                per_source[key] = {"status": "failed", "error": str(err)}
                print(f"[fail] {vp.name}: {err}", file=sys.stderr)
                if not args.no_manifest:
                    append_manifest_jsonl(
                        manifest_jsonl,
                        manifest_row(
                            vp=vp,
                            output_dir=output_dir,
                            response_format=args.response_format,
                            status="failed",
                            error=str(err),
                        ),
                        manifest_lock,
                    )

    if not args.no_manifest:
        manifest_path = output_dir / "transcription-manifest.json"
        manifest = {
            "outputDir": str(output_dir.resolve()),
            "responseFormat": args.response_format,
            "model": args.model,
            "manifestJsonl": manifest_jsonl.name,
            "entries": build_manifest_entries(
                videos=videos,
                output_dir=output_dir,
                response_format=args.response_format,
                per_source=per_source,
            ),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        print(f"Wrote manifest: {manifest_path} (incremental log: {manifest_jsonl})", flush=True)

    print(f"Done. ok={ok} skipped={skipped} failed={len(failed)}", flush=True)
    if failed:
        for line in failed:
            print(line, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
