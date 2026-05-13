from vlm.notes import parse_review_notes
from vlm.twelvelabs import normalize_identified_shots, segment_definitions_with_extra_context


def test_normalize_identified_shots_keeps_high_confidence_food_dish_name():
    shots = normalize_identified_shots(
        {
            "identified_shots": [
                {
                    "start_time": 0.0,
                    "end_time": 3.0,
                    "metadata": {
                        "vlm_tag": "the_interaction",
                        "key_instant_start_sec": 1.2,
                        "dish_name": "wagyu katsu sando",
                        "reasoning": "Lifts the sandwich to reveal filling texture.",
                    },
                }
            ]
        }
    )
    assert len(shots) == 1
    assert shots[0].dish_name == "wagyu katsu sando"


def test_normalize_identified_shots_preserves_dish_name_when_provided():
    shots = normalize_identified_shots(
        {
            "identified_shots": [
                {
                    "start_time": 0.0,
                    "end_time": 3.0,
                    "metadata": {
                        "vlm_tag": "establishing_interior",
                        "key_instant_start_sec": 1.2,
                        "dish_name": "should not pass through",
                        "reasoning": "Shows ambient interior lighting and decor.",
                    },
                }
            ]
        }
    )
    assert len(shots) == 1
    assert shots[0].dish_name == "should not pass through"


def test_segment_definition_constrains_dish_name_to_notes_context_names():
    notes_text = """
    restaurant: Fish Cheeks
    location: NoHo
    dishes:
      - name: GRILLED PORK CHEEKS
        description: Marinated in fish sauce, white pepper
      - name: COCONUT CRAB CURRY
        description: Southern style curry with crab meat
      - name: STEAMED FISH WITH THAI HERBS
        description: Whole branzino in cilantro lime broth
    """
    segment_definitions = segment_definitions_with_extra_context(parse_review_notes(notes_text))
    fields = segment_definitions[0]["fields"]
    dish_name_field = next(field for field in fields if field["name"] == "dish_name")

    assert dish_name_field["enum"] == [
        "",
        "GRILLED PORK CHEEKS",
        "COCONUT CRAB CURRY",
        "STEAMED FISH WITH THAI HERBS",
    ]
    assert "Must be one of the dish names listed" not in dish_name_field["description"]
    assert "Use empty string when unknown." in dish_name_field["description"]
    assert "Dish context from reviewer notes (name + description only)." in segment_definitions[0][
        "description"
    ]
