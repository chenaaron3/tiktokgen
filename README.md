# AI Shorts Editor

Local CLI-first MVP for turning food and travel clips into 30-45 second vertical aesthetic b-roll shorts.

## Documents

- `docs/product-spec.md`: MVP product spec.
- `docs/vlm-schema-prototype.md`: rationale and validation plan for the VLM output schema.
- `docs/creative-contract.md`: creative rules for selecting and sequencing footage.

## Prototype Artifacts

- `schemas/edit-plan.schema.json`: minimal Remotion edit-plan schema.
- `scripts/vlm/schema.py`: Pydantic models for VLM analysis JSON (`model_json_schema()`, `model_validate()`).

## Python Modules

Shared Python code is grouped under `scripts/`:

- `scripts/vlm/`: VLM analysis, media probing, TwelveLabs provider, and VLM schema exports.
- `scripts/edit/`: edit-plan generation and edit-plan schema exports.
- `scripts/logger/`: local LiteLLM observability logger.

VLM only (`source` may be **one video** or a **directory**; writes `cache/<run-uuid>/vlm-analysis.json`):

```sh
PYTHONPATH=scripts uv run python -m vlm.analysis path/to/clip.mov
PYTHONPATH=scripts uv run python -m vlm.analysis path/to/folder/of/clips
```

Install dependencies:

```sh
uv sync
npm install
```

Run analysis, edit planning, and Remotion rendering in one command:

```sh
uv run python scripts/render_short.py assets/2026-05-02 \
  --guidance "make this a stylish West Village afternoon"
```

The harness creates a new `cache/<run-id>/` folder, writes `vlm-analysis.json`, `edit-plan.json`, `edit-outline.txt`, LiteLLM observability logs, and renders `render.mp4`. It requires both `TWELVELABS_API_KEY` and `OPENAI_API_KEY` in `.env`.

The VLM stage needs **ffmpeg** when a clip is under TwelveLabs' ~4s minimum: those files are lengthened using a freeze-frame/audio-pad tail, then analyzed; **outputs still reference your original paths and durations.** Each clip payload is the restaurant `identified_shots` taxonomy (`scripts/vlm/schema.py`).

The edit planner validates the VLM JSON, uses LiteLLM to ask for a story outline, then writes an editable `edit-plan.json`. Full LLM request/response payloads are saved under `cache/<run-id>/llm-observability/`.

The edit plan is intentionally small:

- `theme`: H1 story promise and opening hook text.
- `locations`: H2 location sections derived from clip metadata when available.
- `segments`: flat H3 timeline clips linked to locations by `locationId`.
- `text`: sparse timed text overlays.
- `assumptions` and `warnings`: inferred details and caveats.

Open the Remotion Studio/editor:

```sh
npm run dev
```

Render the generated edit plan:

```sh
npm run render -- cache/<run-id>/render.mp4 --props "$(python -c 'from pathlib import Path; print(Path("cache/<run-id>/edit-plan.json").read_text())')"
```

Choose a different output path by changing the first argument after `--`:

```sh
npm run render -- output/my-short.mp4 --props "$(python -c 'from pathlib import Path; print(Path("cache/<run-id>/edit-plan.json").read_text())')"
```

The full pipeline harness runs this package command for you after generating `edit-plan.json`. The first Remotion template renders a 1080x1920 vertical short, sequences the plan's source segments, applies simple crop values, and overlays the theme/text. Voiceover, captions, music, and Whisper timing are intentionally deferred.

To resume a known run folder and skip completed stages, pass `--run-dir`:

```sh
uv run python scripts/render_short.py assets/2026-05-02 \
  --run-dir cache/west-village-test \
  --guidance "make this a stylish West Village afternoon"
```

If `cache/west-village-test/vlm-analysis.json` exists, VLM analysis is skipped. If `cache/west-village-test/edit-plan.json` exists, edit planning is skipped.

You can pass through common controls:

```sh
uv run python scripts/render_short.py assets/2026-05-02 \
  --run-dir cache/west-village-test \
  --guidance "make this a stylish West Village afternoon" \
  --max-concurrency 3 \
  --target-duration 30 \
  --render-output output/west-village.mp4
```
