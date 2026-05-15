"""Shared shot-label helpers for normalization and verification."""

from __future__ import annotations

from vlm.restaurant_tags import FOOD_DISH_TAGS
from vlm.schema import IdentifiedShot


def sanitize_dish_name(shot: IdentifiedShot) -> IdentifiedShot:
    if shot.vlm_tag in FOOD_DISH_TAGS:
        return shot
    if shot.dish_name:
        return shot.model_copy(update={"dish_name": None})
    return shot
