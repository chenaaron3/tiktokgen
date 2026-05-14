"""Agent-review orchestrator with deterministic review/patch loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from edit.assemble import build_resolved_sentences
from edit.agent_review.common import MAX_AGENT_ITERATIONS, hashable_json, now_iso
from edit.agent_review.context import ToolRuntimeContext
from edit.agent_review.models import AgentReviewInputs
from edit.agent_review.review_process import ReviewProcess
from edit.schema_shot_match import SentenceAssignment, ShotMatch
from logger import install_local_observability_logger
from util import PathUtil
from vlm.schema import VlmAnalysis
from contracts import SentenceLedger, WordToken


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class LitellmAgentReviewOrchestrator:
    """Single encapsulated pipeline stage after shot-match generation."""

    def __init__(self, paths: PathUtil, load_env_path: Path | None = None) -> None:
        load_dotenv(load_env_path or PROJECT_ROOT / ".env")
        self._paths = paths

    def refine_shot_match(
        self,
        *,
        shot_match: ShotMatch,
        analysis: VlmAnalysis,
        ledger: SentenceLedger,
        words: list[WordToken],
        voiceover_static_path: str,
        audio_duration_sec: float,
        hook_text: str,
        use_cache: bool = True,
    ) -> ShotMatch:
        state_path = self._paths.agent_review_state_json()
        shot_path = self._paths.shot_match_json()
        expected_input_hash = hashable_json(shot_match.model_dump(by_alias=True))

        if use_cache and state_path.is_file() and shot_path.is_file():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                if state.get("status") == "pass" and state.get("inputHash") == expected_input_hash:
                    print(f"\n==> agent_review (cached: {state_path})")
                    return ShotMatch.model_validate(json.loads(shot_path.read_text(encoding="utf-8")))
            except Exception:
                pass

        print("\n==> agent_review (deterministic loop)")
        install_local_observability_logger()
        self._paths.llm_observability_dir().mkdir(parents=True, exist_ok=True)

        context = ToolRuntimeContext.create(
            paths=self._paths,
            inputs=AgentReviewInputs(
                analysis=analysis,
                ledger=ledger,
                words=words,
                voiceover_static_path=voiceover_static_path,
                audio_duration_sec=audio_duration_sec,
                hook_text=hook_text,
            ),
            shot_match=shot_match,
        )

        final_status = "max_iterations_reached"
        for agent_iteration in range(1, MAX_AGENT_ITERATIONS + 1):
            review_result = ReviewProcess(context=context, iteration=agent_iteration).run()
            self._log_tool_call(
                iteration=agent_iteration,
                tool_name="review_render",
                args={},
                result=review_result,
            )
            if bool(review_result.get("passed")):
                final_status = "pass"
                break
            replacements = review_result.get("suggestedAssignments")
            if not isinstance(replacements, list) or not replacements:
                final_status = "no_suggestions"
                break
            apply_result = self._apply_suggested_assignments(
                context=context,
                replacements=replacements,
            )
            self._log_tool_call(
                iteration=agent_iteration,
                tool_name="apply_suggested_assignments",
                args={"suggestedAssignments": replacements},
                result=apply_result,
            )
            if not bool(apply_result.get("applied")):
                final_status = "replace_failed"
                break

        final_shot_match = context.shot_match
        shot_path.write_text(
            json.dumps(final_shot_match.model_dump(by_alias=True), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {
                    "status": final_status,
                    "inputHash": expected_input_hash,
                    "planVersion": context.plan_version,
                    "passedSentenceIds": sorted(context.passed_sentence_ids),
                    "completedAt": now_iso(),
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return final_shot_match

    def _apply_suggested_assignments(
        self,
        *,
        context: ToolRuntimeContext,
        replacements: list[Any],
    ) -> dict[str, Any]:
        candidate = context.shot_match.model_copy(deep=True)
        assign_map = {row.sentence_id: i for i, row in enumerate(candidate.assignments)}
        updated_ids: list[str] = []
        for raw in replacements:
            try:
                replacement = SentenceAssignment.model_validate(raw)
            except Exception as error:
                return {"applied": False, "error": f"invalid_suggested_assignment: {error}"}
            sentence_id = replacement.sentence_id
            if sentence_id not in assign_map:
                return {"applied": False, "error": f"unknown_sentence: {sentence_id}"}
            idx = assign_map[sentence_id]
            candidate.assignments[idx] = replacement
            updated_ids.append(sentence_id)

        if not updated_ids:
            return {"applied": False, "error": "no_updates"}

        try:
            build_resolved_sentences(
                shot_match=candidate,
                analysis=context.inputs.analysis,
                sentence_ledger=context.inputs.ledger,
                audio_duration_sec=context.inputs.audio_duration_sec,
            )
        except Exception as error:
            return {"applied": False, "error": f"semantic_validation_failed: {error}"}

        context.shot_match = candidate
        context.plan_version += 1
        for sid in updated_ids:
            context.passed_sentence_ids.discard(sid)
        return {
            "applied": True,
            "planVersion": context.plan_version,
            "updatedSentenceIds": updated_ids,
        }

    def _log_tool_call(self, *, iteration: int, tool_name: str, args: dict[str, Any], result: dict[str, Any]) -> None:
        log_path = self._paths.agent_review_tools_jsonl()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": now_iso(),
            "iteration": iteration,
            "toolName": tool_name,
            "args": args,
            "result": result,
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

