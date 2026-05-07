"""LLM-backed script generation (LiteLLM)."""

from __future__ import annotations

import os
from pathlib import Path

import litellm
from dotenv import load_dotenv

from logger import install_local_observability_logger
from narrative.providers import ScriptGenerator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROMPT_PATH = PROJECT_ROOT / "prompts" / "script_generator.md"
DEFAULT_MODEL = "openai/gpt-4.1"


def _load_prompt(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text().strip()


class LitellmScriptGenerator(ScriptGenerator):
    def __init__(
        self,
        *,
        model: str | None = None,
        prompt_path: Path | None = None,
        observability_path: str | Path | None = None,
        dotenv_path: Path | None = None,
    ) -> None:
        load_dotenv(dotenv_path or PROJECT_ROOT / ".env")
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required in the environment or .env")
        self._model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
        self._prompt_path = prompt_path or DEFAULT_PROMPT_PATH
        self._obs_path = Path(observability_path) if observability_path else None
        if self._obs_path is not None:
            install_local_observability_logger()

    def generate(self, notes: str) -> str:
        notes = notes.strip()
        if not notes:
            raise ValueError("Notes are empty")
        system_prompt = _load_prompt(self._prompt_path)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": notes},
        ]
        metadata = None
        if self._obs_path is not None:
            metadata = {"stage": "script_generator", "observabilityPath": str(self._obs_path)}
        kwargs: dict = {"model": self._model, "messages": messages}
        if metadata is not None:
            kwargs["metadata"] = metadata
        response = litellm.completion(**kwargs)
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("LiteLLM returned an empty response")
        return content.strip()
