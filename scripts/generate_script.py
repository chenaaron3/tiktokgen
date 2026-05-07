#!/usr/bin/env python3
"""Thin CLI shim — delegates to narrative.script_generator."""

from __future__ import annotations

from pathlib import Path
import argparse
import sys

from narrative.script_generator import LitellmScriptGenerator, PROJECT_ROOT, DEFAULT_PROMPT_PATH, DEFAULT_MODEL

# Re-export constants for argparse help text
GPT_4O = DEFAULT_MODEL


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a TikTok-style restaurant review script from rough notes.",
    )
    parser.add_argument("notes_file", nargs="?", type=Path)
    parser.add_argument("--notes")
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--prompt", type=Path, help=f"Defaults to {DEFAULT_PROMPT_PATH}")
    parser.add_argument("--model", help=f"Defaults to OPENAI_MODEL or {DEFAULT_MODEL}")
    parser.add_argument("--no-observability", action="store_true")
    return parser.parse_args()


def read_notes(args: argparse.Namespace) -> tuple[str, Path | None]:
    if args.notes_file is not None:
        path = args.notes_file.expanduser()
        if str(path) == "-":
            return sys.stdin.read(), None
        return path.read_text(), path.resolve()
    if not sys.stdin.isatty():
        return sys.stdin.read(), None
    if args.notes:
        return args.notes, None
    raise SystemExit("Provide notes via file, stdin, or --notes.")


def main() -> int:
    args = parse_args()
    notes, notes_ref = read_notes(args)
    out = args.output.expanduser().resolve() if args.output else None
    obs = None
    if not args.no_observability:
        base = out.parent if out else (notes_ref.parent if notes_ref else Path.cwd())
        obs_dir = base / "llm-observability"
        obs_dir.mkdir(parents=True, exist_ok=True)
        obs = obs_dir / "script.json"

    gen = LitellmScriptGenerator(
        model=args.model,
        prompt_path=args.prompt,
        observability_path=obs,
        dotenv_path=PROJECT_ROOT / ".env",
    )
    script = gen.generate(notes)
    if out:
        out.write_text(script + "\n")
        print(f"Wrote script: {out}", file=sys.stderr)
    else:
        print(script)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
