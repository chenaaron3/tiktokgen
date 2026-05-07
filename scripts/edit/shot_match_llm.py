"""One-call LiteLLM orchestration → validated ShotMatch."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import litellm
from dotenv import load_dotenv
from pydantic import ValidationError

from edit.providers import ShotMatchOrchestrator
from edit.schema_shot_match import ShotMatch
from edit.strict_json import make_openai_strict_schema
from logger import install_local_observability_logger

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = "openai/gpt-4.1-mini"


def _chat_completion_json(
    *,
    model: str,
    messages: list[dict[str, str]],
    response_format: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> str:
    kwargs: dict[str, Any] = {"model": model, "messages": messages, "response_format": response_format}
    if metadata is not None:
        kwargs["metadata"] = metadata
    response = litellm.completion(**kwargs)
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("LiteLLM returned an empty response")
    return content


class LitellmShotMatchOrchestrator:
    """Production implementation using OpenAI-style JSON schema mode via LiteLLM."""

    def __init__(
        self,
        *,
        model: str | None = None,
        observability_path: Path | None = None,
        load_env_path: Path | None = None,
    ) -> None:
        load_dotenv(load_env_path or PROJECT_ROOT / ".env")
        self._model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
        self._observability_path = observability_path
        if observability_path is not None:
            install_local_observability_logger()

    def generate_shot_match(
        self,
        *,
        sentences: list[dict[str, Any]],
        vlm_shots: list[dict[str, Any]],
        guidance: str | None,
    ) -> ShotMatch:
        schema = make_openai_strict_schema(ShotMatch.model_json_schema(by_alias=True))
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "shot_match",
                "schema": schema,
                "strict": True,
            },
        }
        system_prompt = (
            "You pick b-roll shots for a TikTok-style restaurant voiceover. "
            "Return strict JSON only. Every sentence must reference exactly beatCount shots in order. "
            "Do not repeat the same (clipId,momentId) on consecutive beats across the whole edit. "
            "Prefer higher confidenceScore; use weaker shots only if nothing else fits."
        )
        payload = {
            "guidance": guidance,
            "sentences": sentences,
            "vlmShots": vlm_shots,
        }
        metadata = None
        if self._observability_path is not None:
            metadata = {"stage": "shot_match", "observabilityPath": str(self._observability_path)}
        raw = _chat_completion_json(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format=response_format,
            metadata=metadata,
        )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"LLM returned invalid JSON: {error}") from error

        if "schemaVersion" not in data:
            data["schemaVersion"] = "0.2.0"

        try:
            return ShotMatch.model_validate(data)
        except ValidationError as error:
            raise RuntimeError(f"LLM JSON failed validation: {error}") from error


class StaticShotMatchOrchestrator:
    """Deterministic mock for tests."""

    def __init__(self, fixed: ShotMatch) -> None:
        self._fixed = fixed

    def generate_shot_match(
        self,
        *,
        sentences: list[dict[str, Any]],
        vlm_shots: list[dict[str, Any]],
        guidance: str | None,
    ) -> ShotMatch:
        return self._fixed.model_copy(deep=True)
