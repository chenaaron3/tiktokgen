"""Thin LiteLLM wrapper used across agent-review modules."""

from __future__ import annotations

from typing import Any

import litellm


def run_litellm_completion(
    *,
    model: str,
    messages: list[dict[str, Any]],
    metadata: dict[str, Any],
    response_format: dict[str, Any] | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> Any:
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "metadata": metadata,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    if tools is not None:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    return litellm.completion(**kwargs)

