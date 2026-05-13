from narrative.script_format import split_script_title_and_body


def test_split_script_title_and_body_extracts_hash_title():
    title, body = split_script_title_and_body(
        "# Hidden gem rooftop bar\nWe started with skewers.\nThen noodles."
    )
    assert title == "Hidden gem rooftop bar"
    assert body == "We started with skewers.\nThen noodles."


def test_split_script_title_and_body_preserves_script_when_no_title():
    script = "We started with skewers.\nThen noodles."
    title, body = split_script_title_and_body(script)
    assert title is None
    assert body == script


def test_split_script_title_and_body_uses_first_non_empty_line():
    title, body = split_script_title_and_body(
        "\n\n# A5 Wagyu tasting\nFirst bite was unreal."
    )
    assert title == "A5 Wagyu tasting"
    assert body == "First bite was unreal."
