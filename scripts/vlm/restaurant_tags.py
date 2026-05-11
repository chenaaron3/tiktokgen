"""Shared restaurant-review VLM tag vocabulary and segment prompt text."""

from __future__ import annotations

# Single source of truth for TwelveLabs enum and Pydantic validation.
RESTAURANT_VLM_TAGS: tuple[str, ...] = (
    "establishing_exterior",
    "establishing_interior",
    "the_serve",
    "the_preparation",
    "texture_macro",
    "the_interaction",
    "the_cross_section",
    "the_bite",
    "the_reaction",
    "receipt_shot",
    "not_suitable",
)

# Micro-glossary aligned to author CONTEXT/BUILD/CLIMAX/DATA table (+not_suitable); TwelveLabs caps total text.
_REST_DEFS: tuple[tuple[str, str], ...] = (
    # Vibes (Restaurant Level)
    ("establishing_exterior", "Building facade, signage"),
    ("establishing_interior", "Restaurant decor, lighting"),
    
    # Food Preparation (Server Action)
    ("the_serve", "Server's hands placing the dish onto the table."),
    ("the_preparation", "Server actively modifying the dish: pouring broth, plating, or cooking."),
    
    # Food Interaction (User Action)
    ("texture_macro", "Close-up of untouched food, locked focus on surface details"),
    ("the_interaction", "User manipulating food: lifting with chopsticks, stirring, or dipping."),
    ("the_cross_section", "Food being sliced or pulled apart to reveal internal layers."),
    
    # Food Reaction
    ("the_bite", "Subject actively taking a bite of the food."),
    ("the_reaction", "Clear facial expression showing a reaction after tasting."),
    
    # Informational
    ("receipt_shot", "Legible, stable close-up of the printed bill or price menu."),
    
    # General
    ("not_suitable", "Unusable footage: blurry, excessively shaky, dark, or obstructed."),
)

_REST_RULES = "B-roll: one slug each seg; key in [start,end]; Types:: "


def build_restaurant_segment_description() -> str:
    return _REST_RULES + "|".join(f"{s}:{t}" for s, t in _REST_DEFS)


_CANDIDATE_DESCRIPTION = build_restaurant_segment_description().strip()
# if len(_CANDIDATE_DESCRIPTION) > 900:
#     raise RuntimeError(f"Restaurant segment prompt too large ({len(_CANDIDATE_DESCRIPTION)} chars) for TwelveLabs.")

RESTAURANT_SEGMENT_DESCRIPTION = _CANDIDATE_DESCRIPTION
