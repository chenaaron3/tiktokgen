"""Helpers for parsing script text into visual title + spoken narration."""

from __future__ import annotations


def split_script_title_and_body(script_text: str) -> tuple[str | None, str]:
    """Parse an optional `# Title` first line from script text.

    Rules:
    - Only the first non-empty line can define a title.
    - A title line begins with `#` and is excluded from narration.
    - Returned title is normalized without the leading `#` and surrounding spaces.
    - If no title is present, title is ``None`` and body is unchanged.
    """

    lines = script_text.splitlines()
    first_non_empty_idx = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first_non_empty_idx is None:
        return None, ""

    first_non_empty = lines[first_non_empty_idx].strip()
    if not first_non_empty.startswith("#"):
        return None, script_text

    title = first_non_empty.lstrip("#").strip()
    body_lines = lines[:first_non_empty_idx] + lines[first_non_empty_idx + 1 :]
    body = "\n".join(body_lines).strip()
    return title, body
