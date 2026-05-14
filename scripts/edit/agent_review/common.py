"""Shared constants and helpers for agent-review package."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AGENT_REVIEW_MODEL = "openai/gpt-4.1-mini"
AGENT_JUDGE_MODEL = "openai/gpt-4.1-mini"
MAX_AGENT_TURNS = 24
MAX_AGENT_ITERATIONS = 3
_SHOT_GENERATOR_PROMPT_PATH = PROJECT_ROOT / "prompts" / "shot_generator.md"
SHOT_GENERATOR_CONTEXT = _SHOT_GENERATOR_PROMPT_PATH.read_text(encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def shot_cache_key(clip_id: str, shot_id: str) -> str:
    return f"{clip_id}::{shot_id}"


def hashable_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

