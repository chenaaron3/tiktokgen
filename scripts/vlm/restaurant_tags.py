"""Shared restaurant-review VLM tag vocabulary and segment prompt text."""

from __future__ import annotations

# Single source of truth for TwelveLabs enum and Pydantic validation.
RESTAURANT_VLM_TAGS: tuple[str, ...] = (
    "establishing_exterior",
    "negative_space_interior",
    "kinetic_ambience",
    "the_drop",
    "action_pour",
    "kitchen_sizzle",
    "utensil_lift",
    "the_cross_section",
    "the_mix",
    "texture_macro",
    "menu_scan",
    "receipt_shot",
    "queue_wait",
    "not_suitable",
)

# Micro-glossary aligned to author CONTEXT/BUILD/CLIMAX/DATA table (+not_suitable); TwelveLabs caps total text.
_REST_DEFS: tuple[tuple[str, str], ...] = (
    ("establishing_exterior", "wide static curb façade exterior."),
    ("negative_space_interior", "calm vignette décor neg-space idle no hero diner."),
    ("kinetic_ambience", "sharp dish fg blur bg crowd motion."),
    ("the_drop", "hands lowers dish/glass to table contact."),
    ("action_pour", "pour broth/sauce/drink onto/in food."),
    ("kitchen_sizzle", "steam hiss or fry sizzle in cookware."),
    ("utensil_lift", "utensil lifts bite vertical."),
    ("the_cross_section", "horizontal slice/pull reveals layers."),
    ("the_mix", "overhead toss/stir fold mix."),
    ("texture_macro", "macro locked glaze/crisp/crumb surface."),
    ("menu_scan", "legible menu prices text."),
    ("receipt_shot", "bill paper total readable."),
    ("queue_wait", "sidewalk façade queue/outside wait."),
    ("not_suitable", "blur OOF dark empty sway discard."),
)

_REST_RULES = "B-roll: one slug each seg; key in [start,end]; Types:: "


def build_restaurant_segment_description() -> str:
    return _REST_RULES + "|".join(f"{s}:{t}" for s, t in _REST_DEFS)


_CANDIDATE_DESCRIPTION = build_restaurant_segment_description().strip()
if len(_CANDIDATE_DESCRIPTION) > 900:
    raise RuntimeError(f"Restaurant segment prompt too large ({len(_CANDIDATE_DESCRIPTION)} chars) for TwelveLabs.")

RESTAURANT_SEGMENT_DESCRIPTION = _CANDIDATE_DESCRIPTION
