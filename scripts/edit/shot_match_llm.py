"""One-call LiteLLM orchestration → validated ``ShotMatch`` (idempotent on ``shot-match.json``)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import litellm
from dotenv import load_dotenv
from pydantic import ValidationError

from contracts import SentenceLedger
from edit.schema_shot_match import ShotMatch
from edit.strict_json import make_openai_strict_schema
from edit.vlm_shots import build_vlm_shots_for_prompt
from logger import install_local_observability_logger
from util import PathUtil
from vlm.schema import VlmAnalysis

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SHOT_MATCH_MODEL = "openai/gpt-4.1-mini"


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
    """Caches ``shot-match.json`` under ``paths``; observability handled when calling LiteLLM."""

    def __init__(self, paths: PathUtil, load_env_path: Path | None = None) -> None:
        load_dotenv(load_env_path or PROJECT_ROOT / ".env")
        self._paths = paths

    def generate_shot_match(
        self,
        *,
        analysis: VlmAnalysis,
        ledger: SentenceLedger,
        guidance: str | None,
    ) -> ShotMatch:
        shot_path = self._paths.shot_match_json()
        if shot_path.is_file():
            print(f"\n==> shot-match (cached: {shot_path})")
            data = json.loads(shot_path.read_text())
            return ShotMatch.model_validate(data)

        print("\n==> Shot-match LLM")
        self._paths.llm_observability_dir().mkdir(parents=True, exist_ok=True)
        obs_file = self._paths.shot_match_llm_observability_json().resolve()
        install_local_observability_logger()

        sentences_payload = [s.model_dump(by_alias=True) for s in ledger.sentences]
        vlm_shots = build_vlm_shots_for_prompt(analysis)

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
            "Return strict JSON only. Populate assignments: one entry per narration sentence "
            "(sentenceId, text copied verbatim from the input, shots). "
            "Each entry must have exactly beatCount shots in speech order. "
            "Do not repeat the same (clipId,shotId) on consecutive beats across the whole edit. "
            "Prefer higher confidenceScore; use weaker shots only if nothing else fits."
        )
        payload = {
            "guidance": guidance,
            "sentences": sentences_payload,
            "vlmShots": vlm_shots,
        }
        metadata = {"stage": "shot_match", "observabilityPath": str(obs_file)}
        raw = _chat_completion_json(
            model=SHOT_MATCH_MODEL,
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

        try:
            shot_match = ShotMatch.model_validate(data)
        except ValidationError as error:
            raise RuntimeError(f"LLM JSON failed validation: {error}") from error

        shot_path.write_text(
            json.dumps(shot_match.model_dump(by_alias=True), indent=2, ensure_ascii=False) + "\n"
        )
        return shot_match


class StaticShotMatchOrchestrator:
    """Deterministic mock for tests."""

    def __init__(self, fixed: ShotMatch) -> None:
        self._fixed = fixed

    def generate_shot_match(
        self,
        *,
        analysis: VlmAnalysis,
        ledger: SentenceLedger,
        guidance: str | None,
    ) -> ShotMatch:
        return self._fixed.model_copy(deep=True)
