import pytest
from pydantic import ValidationError

from vlm.notes import parse_review_notes


def test_parse_review_notes_strict_schema_fields():
    notes_text = """
    restaurant: Fish Cheeks
    location: NoHo
    vibe: date night spot
    dishes:
      - name: GRILLED PORK CHEEKS
        description: Marinated in fish sauce, white pepper
        thoughts: soft and bouncy
        recommend: true
      - name: COCONUT CRAB CURRY
        description: Southern style curry with crab meat
        recommend: false
    finalThoughts:
      standout: steamed fish
      skip: crab curry
      value: expensive but worth every dollar
    """
    parsed = parse_review_notes(notes_text)
    assert parsed.restaurant == "Fish Cheeks"
    assert parsed.location == "NoHo"
    assert parsed.dishes[0].name == "GRILLED PORK CHEEKS"
    assert parsed.dishes[0].recommend is True
    assert parsed.dishes[1].recommend is False
    assert parsed.final_thoughts is not None
    assert parsed.final_thoughts.standout == "steamed fish"


def test_parse_review_notes_requires_restaurant_location_name_description():
    missing_context = """
    vibe: date night spot
    dishes:
      - name: DISH
        description: DESC
    """
    with pytest.raises(ValidationError):
        parse_review_notes(missing_context)

    missing_dish_description = """
    restaurant: Fish Cheeks
    location: NoHo
    dishes:
      - name: DISH
    """
    with pytest.raises(ValidationError):
        parse_review_notes(missing_dish_description)


def test_parsed_review_notes_contains_dishes_for_minimal_projection():
    notes_text = """
    restaurant: Fish Cheeks
    location: NoHo
    dishes:
      - name: GRILLED PORK CHEEKS
        description: Marinated in fish sauce, white pepper
        thoughts: soft and bouncy
        recommend: true
    """
    parsed = parse_review_notes(notes_text)

    assert [{"name": dish.name, "description": dish.description} for dish in parsed.dishes] == [
        {
            "name": "GRILLED PORK CHEEKS",
            "description": "Marinated in fish sauce, white pepper",
        }
    ]


def test_parse_review_notes_rejects_invalid_yaml():
    with pytest.raises(ValueError):
        parse_review_notes("restaurant: Fish Cheeks: bad")
