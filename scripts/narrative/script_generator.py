"""LLM-backed script generation (LiteLLM).

Used by ``run_pipeline`` with a run ``PathUtil``: ``generate(notes)`` returns
``(hook_text, narration_script)`` parsed from ``script.txt`` when present,
otherwise writes ``script.draft.txt`` via LiteLLM and ``SystemExit(0)`` until approved.
"""

from __future__ import annotations

import os
from pathlib import Path

import litellm
from dotenv import load_dotenv

from logger import install_local_observability_logger
from narrative.providers import ScriptGenerator
from narrative.script_format import split_script_title_and_body
from util import PathUtil

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
        paths: PathUtil,
        *,
        model: str | None = None,
        prompt_path: Path | None = None,
        observability_path: Path | None = None,
        dotenv_path: Path | None = None,
    ) -> None:
        load_dotenv(dotenv_path or PROJECT_ROOT / ".env")
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required in the environment or .env")
        self._paths = paths
        self._model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
        self._prompt_path = prompt_path or DEFAULT_PROMPT_PATH
        self._obs_path = (observability_path or paths.script_llm_observability_json()).resolve()
        self._obs_path.parent.mkdir(parents=True, exist_ok=True)
        install_local_observability_logger()

    def generate(self, notes: str, *, use_cache: bool = True) -> tuple[str, str]:
        notes = notes.strip()
        approved = self._paths.script_txt()
        if use_cache and approved.is_file():
            return self._parse_script(approved.read_text())

        if not notes:
            raise ValueError("Notes are empty")

        text = self._complete_via_litellm(notes)
        draft = self._paths.script_draft_txt()
        draft.write_text(text.strip() + "\n")
        print(f"Wrote script draft: {draft}")
        print("Copy or rename script.draft.txt → script.txt before continuing.")
        raise SystemExit(0)

    def _parse_script(self, script_text: str) -> tuple[str, str]:
        hook_text, narration_script = split_script_title_and_body(script_text)
        if not narration_script.strip():
            raise RuntimeError("script narration is empty after removing optional title line")
        return (hook_text or "", narration_script)

    def _complete_via_litellm(self, notes: str) -> str:
        system_prompt = _load_prompt(self._prompt_path)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": notes},
        ]
        metadata = {"stage": "script_generator", "observabilityPath": str(self._obs_path)}
        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "metadata": metadata,
        }
        response = litellm.completion(**kwargs)
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("LiteLLM returned an empty response")
        return content.strip()
