"""Adapt Pydantic JSON Schema for OpenAI-style strict structured output."""

from __future__ import annotations

from typing import Any


def make_openai_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Recursively add required=all keys and forbid additionalProperties."""
    if schema.get("type") == "object" and isinstance(schema.get("properties"), dict):
        schema["required"] = list(schema["properties"].keys())
        schema["additionalProperties"] = False

    schema.pop("default", None)

    for key in ("properties", "$defs"):
        nested = schema.get(key)
        if isinstance(nested, dict):
            for value in nested.values():
                if isinstance(value, dict):
                    make_openai_strict_schema(value)

    for key in ("items", "anyOf", "oneOf", "allOf"):
        nested = schema.get(key)
        if isinstance(nested, dict):
            make_openai_strict_schema(nested)
        elif isinstance(nested, list):
            for value in nested:
                if isinstance(value, dict):
                    make_openai_strict_schema(value)

    return schema
