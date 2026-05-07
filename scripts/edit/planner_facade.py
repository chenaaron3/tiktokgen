"""High-level API: build prompt rows + call orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from contracts import SentenceLedger
from edit.providers import ShotMatchOrchestrator
from edit.schema_shot_match import ShotMatch
from edit.shot_match_llm import LitellmShotMatchOrchestrator
from edit.vlm_shots import build_vlm_shots_for_prompt
from vlm.schema import VlmAnalysis


def run_shot_match(
    *,
    analysis: VlmAnalysis,
    ledger: SentenceLedger,
    orchestrator: ShotMatchOrchestrator | None = None,
    guidance: str | None = None,
    model: str | None = None,
    observability_path: Path | None = None,
) -> ShotMatch:
    """Run the single LLM orchestration call unless a mock orchestrator is supplied."""
    orch = orchestrator or LitellmShotMatchOrchestrator(model=model, observability_path=observability_path)

    sentences_payload: list[dict[str, Any]] = [
        s.model_dump(by_alias=True) for s in ledger.sentences
    ]
    vlm_rows = build_vlm_shots_for_prompt(analysis)
    return orch.generate_shot_match(
        sentences=sentences_payload,
        vlm_shots=vlm_rows,
        guidance=guidance,
    )
