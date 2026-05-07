#!/usr/bin/env python3
"""Generate a TikTok-style restaurant review script from rough notes via LLM."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import litellm
from dotenv import load_dotenv

from logger import install_local_observability_logger


CLAUDE_FLAGSHIP = 'anthropic/claude-opus-4-6'
GPT_FLAGSHIP = 'openai/gpt-5.5'
GPT_4O = 'openai/gpt-4.1'
GPT_4O_MINI = 'openai/gpt-4.1-mini'

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROMPT_PATH = PROJECT_ROOT / "prompts" / "script_generator.md"
DEFAULT_MODEL = GPT_4O


def load_system_prompt(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"Prompt file not found: {path}")
    return path.read_text().strip()


def create_chat_completion(
    *,
    model: str,
    messages: list[dict[str, str]],
    metadata: dict[str, str] | None = None,
) -> str:
    kwargs: dict[str, object] = {"model": model, "messages": messages}
    if metadata is not None:
        kwargs["metadata"] = metadata
    response = litellm.completion(**kwargs)
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("LiteLLM returned an empty response")
    return content


def generate_script(
    notes: str,
    *,
    model: str | None = None,
    prompt_path: Path | None = None,
    observability_path: Path | None = None,
) -> str:
    """Return spoken script text from free-form restaurant review notes."""
    load_dotenv(PROJECT_ROOT / ".env")
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required in the environment or .env")

    resolved_prompt = (prompt_path or DEFAULT_PROMPT_PATH).expanduser().resolve()
    system_prompt = load_system_prompt(resolved_prompt)
    planning_model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)

    if observability_path is not None:
        install_local_observability_logger()

    user_content = notes.strip()
    if not user_content:
        raise SystemExit("Notes are empty; provide text describing the restaurant visit.")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    metadata = None
    if observability_path is not None:
        metadata = {"stage": "script_generator", "observabilityPath": str(observability_path)}

    return create_chat_completion(
        model=planning_model,
        messages=messages,
        metadata=metadata,
    ).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a TikTok-style restaurant review script from rough notes."
    )
    parser.add_argument(
        "notes_file",
        nargs="?",
        type=Path,
        help="Path to a text file of notes. Omit to read notes from stdin.",
    )
    parser.add_argument(
        "--notes",
        help="Inline notes string (ignored if notes_file or stdin provides content).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write script to this path. Defaults to stdout.",
    )
    parser.add_argument(
        "--prompt",
        type=Path,
        help=f"System prompt markdown. Defaults to {DEFAULT_PROMPT_PATH}.",
    )
    parser.add_argument(
        "--model",
        help=f"LiteLLM model. Defaults to OPENAI_MODEL or {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--no-observability",
        action="store_true",
        help="Do not write LiteLLM request/response logs to disk.",
    )
    return parser.parse_args()


def read_notes(args: argparse.Namespace) -> tuple[str, Path | None]:
    """Return (notes text, optional path for default observability directory)."""
    if args.notes_file is not None:
        path = args.notes_file.expanduser()
        if str(path) == "-":
            return sys.stdin.read(), None
        try:
            return path.read_text(), path.resolve()
        except OSError as error:
            raise SystemExit(f"Could not read notes file: {error}") from error
    if not sys.stdin.isatty():
        return sys.stdin.read(), None
    if args.notes:
        return args.notes, None
    raise SystemExit(
        "Provide notes via a file path, pipe stdin, or --notes \"...\"."
    )


def main() -> int:
    args = parse_args()
    notes, notes_ref_path = read_notes(args)
    output_path = args.output.expanduser().resolve() if args.output else None

    observability_path = None
    if not args.no_observability:
        base = (
            output_path.parent
            if output_path is not None
            else (notes_ref_path.parent if notes_ref_path is not None else Path.cwd())
        )
        observability_dir = base / "llm-observability"
        observability_path = observability_dir / "script-generator.json"

    script = generate_script(
        notes,
        model=args.model,
        prompt_path=args.prompt,
        observability_path=observability_path,
    )

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(script + "\n")
        print(f"Wrote script: {output_path}", file=sys.stderr)
        if observability_path is not None:
            print(f"Wrote LLM observability: {observability_path.parent}", file=sys.stderr)
    else:
        print(script)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
