"""LiteLLM custom logger for local request/response observability."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import litellm
from litellm.integrations.custom_logger import CustomLogger


class LocalFileObservabilityLogger(CustomLogger):
    """Write LiteLLM calls to JSON files selected by per-request metadata."""

    def log_success_event(self, kwargs: dict[str, Any], response_obj: Any, start_time: Any, end_time: Any) -> None:
        self._write_event(
            event_type="success",
            kwargs=kwargs,
            response_obj=response_obj,
            start_time=start_time,
            end_time=end_time,
        )

    def log_failure_event(self, kwargs: dict[str, Any], response_obj: Any, start_time: Any, end_time: Any) -> None:
        self._write_event(
            event_type="failure",
            kwargs=kwargs,
            response_obj=response_obj,
            start_time=start_time,
            end_time=end_time,
        )

    def _write_event(
        self,
        *,
        event_type: str,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: Any,
        end_time: Any,
    ) -> None:
        metadata = self._metadata(kwargs)
        output_path = metadata.get("observabilityPath")
        if not output_path:
            return

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "stage": metadata.get("stage"),
            "eventType": event_type,
            "loggedAt": datetime.now(timezone.utc).isoformat(),
            "model": kwargs.get("model"),
            "request": {
                "messages": kwargs.get("messages"),
                "responseFormat": kwargs.get("response_format"),
                "metadata": metadata,
            },
            "response": self._json_safe(response_obj),
            "timing": {
                "startTime": str(start_time),
                "endTime": str(end_time),
                "durationSec": self._duration_seconds(start_time, end_time),
            },
            "cost": kwargs.get("response_cost"),
            "cacheHit": kwargs.get("cache_hit"),
        }
        path.write_text(json.dumps(self._json_safe(event), indent=2, ensure_ascii=False) + "\n")

    @staticmethod
    def _metadata(kwargs: dict[str, Any]) -> dict[str, Any]:
        litellm_params = kwargs.get("litellm_params") or {}
        metadata = litellm_params.get("metadata") or kwargs.get("metadata") or {}
        return metadata if isinstance(metadata, dict) else {}

    @staticmethod
    def _duration_seconds(start_time: Any, end_time: Any) -> float | None:
        try:
            return (end_time - start_time).total_seconds()
        except Exception:
            return None

    @classmethod
    def _json_safe(cls, value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return cls._json_safe(value.model_dump(mode="json"))
        if isinstance(value, dict):
            return {str(key): cls._json_safe(item) for key, item in value.items()}
        if isinstance(value, list | tuple):
            return [cls._json_safe(item) for item in value]
        if isinstance(value, str | int | float | bool) or value is None:
            return value
        return str(value)


def install_local_observability_logger() -> None:
    """Register the local logger once without discarding other LiteLLM callbacks."""
    if not any(isinstance(callback, LocalFileObservabilityLogger) for callback in litellm.callbacks):
        litellm.callbacks.append(LocalFileObservabilityLogger())
