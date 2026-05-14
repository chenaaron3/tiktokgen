"""Sentence-level visual review process for agent-review stage."""

from __future__ import annotations

import base64
import json
import math
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from edit.assemble import assemble_render_plan, build_resolved_sentences
from edit.agent_review.common import AGENT_JUDGE_MODEL, SHOT_GENERATOR_CONTEXT, now_iso
from edit.agent_review.context import ToolRuntimeContext
from edit.agent_review.llm import run_litellm_completion
from edit.agent_review.models import (
    ClipReview,
    ReviewRenderResult,
)
from edit.strict_json import make_openai_strict_schema
from edit.vlm_shots import build_vlm_shots_for_prompt


class ReviewProcess:
    """Encapsulates sample extraction, judging, and issue generation."""

    def __init__(self, context: ToolRuntimeContext, iteration: int) -> None:
        self._context = context
        self._iteration = iteration

    def run(self, rubric: str | None = None) -> dict[str, Any]:
        del rubric  # v1 uses a fixed rubric prompt.
        resolved = build_resolved_sentences(
            shot_match=self._context.shot_match,
            analysis=self._context.inputs.analysis,
            sentence_ledger=self._context.inputs.ledger,
            audio_duration_sec=self._context.inputs.audio_duration_sec,
        )
        render_plan = assemble_render_plan(
            resolved_sentences=resolved,
            whisper_words=self._context.inputs.words,
            voiceover_static_path=self._context.inputs.voiceover_static_path,
            audio_duration_sec=self._context.inputs.audio_duration_sec,
            run_id=self._context.inputs.analysis.run_id,
            created_at=now_iso(),
            hook_text=self._context.inputs.hook_text or "",
            paths=None,
        )

        sentence_rows = {row.sentence_id: row for row in self._context.inputs.ledger.sentences}
        beats_by_sentence: dict[str, list[Any]] = defaultdict(list)
        for beat in render_plan.beats:
            beats_by_sentence[beat.sentence_id].append(beat)

        clip_reviews: list[ClipReview] = []
        blocking_issue_found = False
        suggested_assignments: list[Any] = []
        pass_set = set(self._context.passed_sentence_ids)
        current_assignments = {row.sentence_id: row for row in self._context.shot_match.assignments}

        for sentence_id, beats in beats_by_sentence.items():
            if sentence_id in pass_set:
                continue
            sentence = sentence_rows.get(sentence_id)
            if sentence is None:
                continue
            frame_payload: list[dict[str, Any]] = []
            for beat in beats:
                clip_id = beat.clip_id
                shot_id = beat.shot_id
                timestamps = self._sampling_offsets(beat.source_start_sec, beat.source_end_sec)
                frame_paths = self._extract_sample_frames(
                    clip_id=clip_id,
                    shot_id=shot_id,
                    source_path=Path(beat.source_path),
                    timestamps=timestamps,
                )
                for i, frame_path in enumerate(frame_paths):
                    frame_payload.append(
                        {
                            "clipId": clip_id,
                            "shotId": shot_id,
                            "timestampSec": timestamps[min(i, len(timestamps) - 1)],
                            "imageDataUrl": self._data_url(frame_path),
                        }
                    )

            expected_clip_pairs = sorted({(beat.clip_id, beat.shot_id) for beat in beats})
            current_assignment = current_assignments.get(sentence_id)
            judge = self._judge_sentence(
                sentence_id=sentence_id,
                sentence_text=sentence.text,
                frame_payload=frame_payload,
                expected_clip_pairs=expected_clip_pairs,
                beat_count=int(sentence.beat_count),
                current_assignment=current_assignment.model_dump(by_alias=True) if current_assignment else None,
            )
            sentence_reviews = self._normalize_clip_reviews(
                sentence_id=sentence_id,
                expected_clip_pairs=expected_clip_pairs,
                raw_reviews=judge.clip_reviews,
            )
            clip_reviews.extend(sentence_reviews)
            sentence_suggestions = [s for s in judge.suggested_assignments if s.sentence_id == sentence_id]
            sentence_passed = bool(judge.passed) and all(row.passed for row in sentence_reviews)
            if not sentence_passed:
                blocking_issue_found = True
            if not sentence_passed and sentence_suggestions:
                pass_set.discard(sentence_id)
                suggested_assignments.extend(sentence_suggestions)
            elif sentence_passed:
                pass_set.add(sentence_id)
            else:
                pass_set.discard(sentence_id)

        passed = len(suggested_assignments) == 0 and not blocking_issue_found
        self._context.latest_pass = passed
        self._context.passed_sentence_ids = pass_set
        result = ReviewRenderResult.model_validate(
            {
                "passed": passed,
                "clipReviews": [row.model_dump(by_alias=True) for row in clip_reviews],
                "suggestedAssignments": [row.model_dump(by_alias=True) for row in suggested_assignments],
            }
        )
        payload = result.model_dump(by_alias=True)
        payload["passedSentenceIds"] = sorted(pass_set)
        self._context.last_review_result = payload
        return payload

    def _sampling_offsets(self, start_sec: float, end_sec: float) -> list[float]:
        duration = max(0.001, float(end_sec - start_sec))
        sample_count = max(1, int(math.ceil(duration)))
        # Sample at roughly 1 fps using per-second midpoints.
        max_offset = max(duration - 0.001, 0.0)
        offsets = [min((idx + 0.5), max_offset) for idx in range(sample_count)]
        return [start_sec + offset for offset in offsets]

    def _extract_sample_frames(
        self,
        *,
        clip_id: str,
        shot_id: str,
        source_path: Path,
        timestamps: list[float],
    ) -> list[Path]:
        frames_dir = self._context.paths.agent_review_dir() / "frames" / f"{clip_id}__{shot_id}"
        frames_dir.mkdir(parents=True, exist_ok=True)
        out: list[Path] = []
        for i, ts in enumerate(timestamps):
            target = frames_dir / f"frame-{i:02d}.png"
            if not target.is_file():
                self._extract_frame_with_retry(source_path=source_path, timestamp_sec=ts, target=target)
            out.append(target)
        return out

    def _extract_frame_with_retry(self, *, source_path: Path, timestamp_sec: float, target: Path) -> None:
        # ffmpeg can exit 0 near EOF without writing output; step back and retry.
        offsets = [0.0, 0.1, 0.25, 0.5, 1.0]
        attempts: list[tuple[float, str, str]] = []
        for step_back in offsets:
            candidate_ts = max(float(timestamp_sec) - step_back, 0.0)
            cmd = [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{candidate_ts:.6f}",
                "-i",
                str(source_path),
                "-frames:v",
                "1",
                str(target),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            attempts.append((candidate_ts, result.stdout.strip(), result.stderr.strip()))
            if result.returncode != 0:
                continue
            if target.is_file():
                return

        details = "; ".join(
            f"ts={ts:.3f} stdout={stdout!r} stderr={stderr!r}" for ts, stdout, stderr in attempts
        )
        raise RuntimeError(
            f"Failed to extract frame from {source_path} at {timestamp_sec:.3f}s after retries. {details}"
        )

    def _data_url(self, path: Path) -> str:
        data = path.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        return f"data:{mime};base64,{b64}"

    def _judge_sentence(
        self,
        *,
        sentence_id: str,
        sentence_text: str,
        frame_payload: list[dict[str, Any]],
        expected_clip_pairs: list[tuple[str, str]],
        beat_count: int,
        current_assignment: dict[str, Any] | None,
    ) -> ReviewRenderResult:
        schema = make_openai_strict_schema(ReviewRenderResult.model_json_schema(by_alias=True))
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "review_render_result",
                "schema": schema,
                "strict": True,
            },
        }
        prompt_text = (
            "Judge if selected shots visually match the narration sentence intent for this one sentence only. "
            "Return ReviewRenderResult JSON. "
            "Set passed=true only when every reviewed clip matches sentence intent, else passed=false. "
            "Return exactly one clipReviews entry per expected clip for this sentenceId. "
            "Each clipReviews entry must include passed and feedback explaining the decision. "
            "Only populate suggestedAssignments when passed=false; if passed=true return suggestedAssignments=[]. "
            "When proposing suggestedAssignments, prefer to keep the currentAssignment shot-count and per-shot "
            "beatSpan structure unchanged, and replace only clipId/shotId with better candidateShots. "
            "If sentence should change, return at most one SentenceAssignment for this same sentenceId, "
            "whose shot beatSpan total equals targetBeatCount. "
            "Use only candidateShots clipId/shotId values."
        )
        content: list[dict[str, Any]] = [
            {"type": "text", "text": prompt_text},
            {"type": "text", "text": f"sentenceId: {sentence_id}"},
            {"type": "text", "text": f"sentenceText: {sentence_text}"},
            {"type": "text", "text": f"targetBeatCount: {beat_count}"},
        ]
        # if SHOT_GENERATOR_CONTEXT:
        #     content.append(
        #         {
        #             "type": "text",
        #             "text": (
        #                 "Shot selection policy context"
        #                 "(use as editorial constraints while judging/suggesting):\n"
        #                 f"{SHOT_GENERATOR_CONTEXT}"
        #             ),
        #         }
        #     )
        if current_assignment is not None:
            content.append(
                {"type": "text", "text": f"currentAssignment: {json.dumps(current_assignment, ensure_ascii=False)}"}
            )
        content.append(
            {
                "type": "text",
                "text": f"expectedClipPairs: {json.dumps(expected_clip_pairs, ensure_ascii=False)}",
            }
        )
        candidates = self._candidate_pool_for_sentence(sentence_text=sentence_text)
        content.append({"type": "text", "text": f"candidateShots: {json.dumps(candidates, ensure_ascii=False)}"})
        for row in frame_payload:
            content.append(
                {
                    "type": "text",
                    "text": (
                        f"clipId={row['clipId']} shotId={row['shotId']} "
                        f"timestampSec={row['timestampSec']:.3f}"
                    ),
                }
            )
            content.append({"type": "image_url", "image_url": {"url": row["imageDataUrl"]}})

        response = run_litellm_completion(
            model=AGENT_JUDGE_MODEL,
            messages=[
                {"role": "system", "content": "You are a strict video shot semantic judge."},
                {"role": "user", "content": content},
            ],
            response_format=response_format,
            metadata={
                "stage": "agent_review_judge",
                "sentenceId": sentence_id,
                "iteration": self._iteration,
                "observabilityPath": str(
                    self._context.paths.agent_review_llm_observability_json(
                        f"judge-{self._iteration}-{sentence_id}"
                    ).resolve()
                ),
            },
        )
        raw = response.choices[0].message.content
        if not raw:
            raise RuntimeError("Judge returned empty content")
        return ReviewRenderResult.model_validate(json.loads(raw))

    def _normalize_clip_reviews(
        self,
        *,
        sentence_id: str,
        expected_clip_pairs: list[tuple[str, str]],
        raw_reviews: list[ClipReview],
    ) -> list[ClipReview]:
        review_by_pair: dict[tuple[str, str], ClipReview] = {}
        for row in raw_reviews:
            pair = (row.clip_id, row.shot_id)
            if pair in review_by_pair:
                continue
            review_by_pair[pair] = row

        normalized: list[ClipReview] = []
        for clip_id, shot_id in expected_clip_pairs:
            row = review_by_pair.get((clip_id, shot_id))
            if row is None:
                normalized.append(
                    ClipReview.model_validate(
                        {
                            "sentenceId": sentence_id,
                            "clipId": clip_id,
                            "shotId": shot_id,
                            "passed": False,
                            "feedback": "Judge did not return a clip review for this shot.",
                        }
                    )
                )
                continue
            normalized.append(
                ClipReview.model_validate(
                    {
                        "sentenceId": sentence_id,
                        "clipId": clip_id,
                        "shotId": shot_id,
                        "passed": bool(row.passed),
                        "feedback": row.feedback,
                    }
                )
            )
        return normalized

    def _candidate_pool_for_sentence(self, *, sentence_text: str, limit: int = 10) -> list[dict[str, Any]]:
        rows = build_vlm_shots_for_prompt(self._context.inputs.analysis)
        used_pairs = {
            (shot.clip_id, shot.shot_id)
            for assignment in self._context.shot_match.assignments
            for shot in assignment.shots
        }
        query_tokens = set(re.findall(r"[a-zA-Z]+", sentence_text.lower()))
        ranked: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            clip_id = str(row["clipId"])
            shot_id = str(row["shotId"])
            if (clip_id, shot_id) in used_pairs:
                continue
            score = 0.0
            text = " ".join(
                [
                    str(row.get("vlmTag") or ""),
                    str(row.get("reasoning") or ""),
                    str(row.get("dishName") or ""),
                    json.dumps(row.get("semanticContext") or {}, ensure_ascii=False),
                ]
            ).lower()
            for token in query_tokens:
                if token and token in text:
                    score += 1.0
            ranked.append(
                (
                    score,
                    {
                        "clipId": clip_id,
                        "shotId": shot_id,
                        "vlmTag": row.get("vlmTag"),
                        "dishName": row.get("dishName"),
                        "reasoning": row.get("reasoning"),
                        "semanticContext": row.get("semanticContext"),
                    },
                )
            )
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        return [payload for _, payload in ranked[:limit]]

