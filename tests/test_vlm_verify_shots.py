from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vlm.notes import parse_review_notes
from vlm.schema import Clip, ClipMedia, IdentifiedShot, TwelveLabsClipRef
from vlm.shot_labels import sanitize_dish_name
from util.path_util import PathUtil
from vlm.verify_shots import verify_clip_shots


def _run_paths(tmp_path: Path) -> PathUtil:
    run_dir = tmp_path / "assets-test"
    (run_dir / "2_vlm").mkdir(parents=True)
    return PathUtil(run_dir)


def _clip_with_shots(*shots: IdentifiedShot) -> Clip:
    return Clip(
        id="c0",
        sourcePath="/tmp/x.mov",
        originalFilename="x.mov",
        durationSec=10.0,
        capturedAt=None,
        location=None,
        media=ClipMedia.empty(),
        twelveLabs=TwelveLabsClipRef(assetId="a", taskId="t"),
        summary="s",
        identifiedShots=list(shots),
    )


def test_sanitize_dish_name_strips_non_food_tags():
    shot = IdentifiedShot(
        shotId="shot-001",
        startSec=0.0,
        endSec=2.0,
        vlmTag="establishing_interior",
        keyInstantStartSec=1.0,
        dishName="wrong",
        reasoning="Interior.",
        labelConfidence="high",
        verifiedBy="twelvelabs",
    )
    assert sanitize_dish_name(shot).dish_name is None


def test_verify_clip_shots_skips_high_confidence(tmp_path: Path) -> None:
    video = tmp_path / "x.mov"
    video.write_bytes(b"stub")
    shot = IdentifiedShot(
        shotId="shot-001",
        startSec=0.0,
        endSec=2.0,
        vlmTag="texture_macro",
        keyInstantStartSec=1.0,
        dishName="Ramen",
        reasoning="Macro.",
        labelConfidence="high",
        verifiedBy="twelvelabs",
    )
    clip = _clip_with_shots(shot).model_copy(update={"source_path": str(video)})
    verified = verify_clip_shots(
        clip,
        notes=None,
        paths=_run_paths(tmp_path),
    )
    assert verified.identified_shots[0].verified_by == "twelvelabs"
    assert verified.identified_shots[0].dish_name == "Ramen"


@patch("vlm.verify_shots.litellm.completion")
@patch("vlm.verify_shots.extract_frame_jpeg")
def test_verify_clip_shots_escalates_medium_confidence(
    mock_extract: MagicMock,
    mock_completion: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    video = tmp_path / "x.mov"
    video.write_bytes(b"not-a-real-video")

    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"jpeg")
    mock_extract.return_value = frame

    mock_completion.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {
                            "vlmTag": "the_interaction",
                            "dishName": "Ramen",
                            "reasoning": "Verified lift.",
                            "semanticContext": "Diner lifts noodles with chopsticks over a bowl.",
                            "labelConfidence": "high",
                        }
                    )
                )
            )
        ]
    )

    shot = IdentifiedShot(
        shotId="shot-001",
        startSec=0.0,
        endSec=2.0,
        vlmTag="the_interaction",
        keyInstantStartSec=1.0,
        dishName="Wrong",
        reasoning="Guess.",
        labelConfidence="medium",
        verifiedBy="twelvelabs",
    )
    clip = _clip_with_shots(shot).model_copy(update={"source_path": str(video)})

    notes = parse_review_notes(
        """
        restaurant: Test
        location: Here
        dishes:
          - name: Ramen
            description: Noodles
        """
    )

    verified = verify_clip_shots(
        clip,
        notes=notes,
        paths=_run_paths(tmp_path),
    )
    assert verified.identified_shots[0].verified_by == "gpt"
    assert verified.identified_shots[0].dish_name == "Ramen"
    assert verified.identified_shots[0].semantic_context == (
        "Diner lifts noodles with chopsticks over a bowl."
    )
    assert verified.identified_shots[0].label_confidence == "high"
    mock_completion.assert_called_once()
    content = mock_completion.call_args.kwargs["messages"][1]["content"]
    user_payload = json.loads(content[0]["text"])
    assert set(user_payload.keys()) == {"allowedVlmTags", "allowedDishes"}
    assert user_payload["allowedDishes"] == [
        {"name": "Ramen", "description": "Noodles"},
    ]
    assert content[1]["text"] == "Frame at 0.0s on the source clip timeline:"
    assert content[1]["type"] == "text"
    assert content[2]["type"] == "image_url"
    assert content[3]["text"] == "Frame at 1.0s on the source clip timeline:"
    assert content[4]["type"] == "image_url"
