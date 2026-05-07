# VLM Schema Prototype

## Purpose

The VLM schema is a generic map of one or more source videos. It should describe what happens, what is visible, what is said, what is heard, where/when each clip was captured when metadata is available, and which moments are visually usable.

It should not decide how to edit the video. Orchestration, pacing, captions, framing, and final clip selection belong in a later planner.

Schema and serialization are defined in code: `scripts/vlm/schema.py` (`VlmAnalysis`, `Clip`, `IdentifiedShot`). Use `model_json_schema()` / `model_validate()` instead of checking in a standalone JSON Schema file.

## Core Question

Can the VLM identify the parts of a video an editor would want to consider while reviewing footage?

An editor is looking for:

- Clear subjects.
- Clean visual quality.
- Interesting motion or change.
- Useful context.
- Useful spoken words or ambient audio.
- Obvious issues that make a moment harder to use.

## Output Shape

The schema has a `clips` array. Each clip has source metadata and a list of timestamped moments:

```json
{
  "clips": [
    {
      "id": "IMG_0774",
      "sourcePath": "assets/2026-05-02/IMG_0774.MOV",
      "capturedAt": "2026-05-02T18:14:25-04:00",
      "location": {
        "latitude": 40.7128,
        "longitude": -74.006
      },
      "summary": "A lively food market with cooking and crowd ambience.",
      "moments": [
        {
          "startSec": 3.2,
          "endSec": 6.8,
          "description": "Close view of food cooking with steam rising from the grill.",
          "subjects": ["grill", "food", "steam"],
          "actions": ["cooking", "steam rising"],
          "visibleText": [],
          "spokenText": "",
          "audio": ["sizzling", "crowd noise"],
          "quality": "great",
          "issues": [],
          "whyUseful": "Strong sensory food moment with clear subject and visible motion."
        }
      ]
    }
  ]
}
```

## Field Principles

- `description` says what happens.
- `subjects` names what is visible.
- `actions` names what changes or moves.
- `visibleText` captures signs, menus, labels, and other readable text.
- `spokenText` captures useful speech or transcript context.
- `audio` captures non-speech sound cues.
- `quality` is a simple editor-facing usability rating: `great`, `good`, `okay`, or `poor`.
- `issues` lists obvious problems like shaky, blurry, dark, obstructed, or unclear.
- `whyUseful` is a short editor note explaining why the moment may be worth considering.
- `capturedAt` and `location` come from media metadata when available and remain `null` otherwise.

## What Belongs Outside The VLM

Do not put these in the VLM output:

- Hook/detail/context/ending roles.
- Final clip durations.
- Captions or overlay text.
- Crop, framing, or vertical-safe decisions.
- Pacing scores.
- Render instructions.
- Final source ranges for the Remotion edit.

Those are planner/orchestrator responsibilities.

## Planner Handoff

The planner can turn generic moments into an edit plan with simple rules:

- Keep `quality` of `great` or `good`.
- Use `okay` moments only when they provide important context.
- Prefer moments with clear subjects and actions.
- Avoid moments with issues unless they are short or contextually important.
- Use `spokenText`, `visibleText`, and `audio` as context for captions or voiceover later.

## Validation Criteria

A VLM output is useful when it:

- Produces coherent timestamped moments.
- Describes content in plain language.
- Captures speech and ambient audio when available.
- Separates useful moments from poor moments with a simple quality label.
- Explains usefulness without making editing decisions.
