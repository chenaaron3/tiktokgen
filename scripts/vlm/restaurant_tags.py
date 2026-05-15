"""Shared restaurant-review VLM tag vocabulary and segment prompt text."""

from __future__ import annotations

# Single source of truth for TwelveLabs enum and Pydantic validation.
FOOD_DISH_TAGS: frozenset[str] = frozenset(
    {
        "the_serve",
        "the_preparation",
        "texture_macro",
        "the_interaction",
        "the_cross_section",
        "the_bite",
        "the_reaction",
    }
)

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
    "info_shot",
    "not_suitable",
)

# Micro-glossary aligned to author CONTEXT/BUILD/CLIMAX/DATA table (+not_suitable); TwelveLabs caps total text.
_REST_DEFS: tuple[tuple[str, str], ...] = (
    # Vibes (Restaurant Level)
    ("establishing_exterior", "Building facade, signage"),
    ("establishing_interior", "Restaurant decor, lighting"),
    
    # Food Preparation (Server Action)
    (
        "the_serve",
        "Server hands placing dish; food sharp, ~2/3 of frame, stays in shot (not drifting in/out).",
    ),
    (
        "the_preparation",
        "Server modifying dish (pour/plate/cook); food sharp, ~2/3 of frame, stable framing.",
    ),

    # Food Interaction (User Action)
    (
        "texture_macro",
        "Untouched food close-up; sharp focus, food ~2/3 of frame with clear surface detail.",
    ),
    (
        "the_interaction",
        "User moves food with hands/utensils; food stays sharp and mostly in frame (~2/3), not slipping in/out.",
    ),
    (
        "the_cross_section",
        "Slicing/pulling apart to show interior; food sharp, ~2/3 of frame, continuous framing.",
    ),
    
    # Food Reaction
    ("the_bite", "Subject actively taking a bite of the food."),
    ("the_reaction", "Clear facial expression showing a reaction after tasting."),
    
    # Informational
    ("info_shot", "Legible, stable close-up of menu prices, printed bill, or receipt."),
    
    # General
    ("not_suitable", "Blurry/out-of-focus/motion-blur, too dark, very shaky, or obstructed."),
)

_HARD_RULES = (
    "RULES: Noticeably blurry, soft-focus, or heavy motion-blur footage must be tagged not_suitable only—do not stretch it into food or establishing tags. "
    "When unsure whether quality is acceptable, choose not_suitable rather than a flattering tag. "
    "For the_preparation, texture_macro, the_interaction, the_cross_section: food must stay in focus and occupy about 2/3 of the frame; "
    "if the food repeatedly enters and leaves frame or is rarely visible, tag not_suitable. "
)
_REST_RULES = _HARD_RULES + "B-roll: one slug each seg; key in [start,end]; Types:: "


def build_restaurant_segment_description() -> str:
    return _REST_RULES + "|".join(f"{s}:{t}" for s, t in _REST_DEFS)


_CANDIDATE_DESCRIPTION = build_restaurant_segment_description().strip()
# if len(_CANDIDATE_DESCRIPTION) > 900:
#     raise RuntimeError(f"Restaurant segment prompt too large ({len(_CANDIDATE_DESCRIPTION)} chars) for TwelveLabs.")

RESTAURANT_SEGMENT_DESCRIPTION = _CANDIDATE_DESCRIPTION
