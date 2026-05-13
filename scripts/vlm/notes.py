"""Structured parser for restaurant review notes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator
from yaml import YAMLError, safe_load


class DishNotes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    thoughts: str | None = None
    recommend: bool | None = None

    @field_validator("name", "description")
    @classmethod
    def required_string_fields_must_not_be_empty(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("required field must not be empty")
        return cleaned

    @field_validator("thoughts")
    @classmethod
    def optional_text_fields_are_normalized(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned or None


class FinalThoughts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    standout: str | None = None
    skip: str | None = None
    value: str | None = None

    @field_validator("standout", "skip", "value")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned or None


class ParsedReviewNotes(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    restaurant: str
    location: str
    vibe: str | None = None
    dishes: list[DishNotes] = Field(min_length=1)
    final_thoughts: FinalThoughts | None = Field(default=None, alias="finalThoughts")

    @field_validator("restaurant", "location")
    @classmethod
    def required_context_fields_must_not_be_empty(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("required field must not be empty")
        return cleaned

    @field_validator("vibe")
    @classmethod
    def normalize_vibe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned or None


def parse_review_notes(notes_text: str) -> ParsedReviewNotes:
    """Parse YAML review notes into a strict structured schema."""
    try:
        payload = safe_load(notes_text)
    except YAMLError as exc:
        raise ValueError("notes.yaml must contain valid YAML") from exc
    if not isinstance(payload, dict):
        raise ValueError("notes.yaml must be a mapping/object at the top level")
    return ParsedReviewNotes.model_validate(payload)
