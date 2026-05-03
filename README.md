# AI Shorts Editor

Local CLI-first MVP for turning food and travel clips into 30-45 second vertical aesthetic b-roll shorts.

## Documents

- `docs/product-spec.md`: MVP product spec.
- `docs/vlm-schema-prototype.md`: rationale and validation plan for the VLM output schema.
- `docs/creative-contract.md`: creative rules for selecting and sequencing footage.

## Prototype Artifacts

- `schemas/vlm-analysis.schema.json`: provider-neutral VLM analysis schema.
- `examples/vlm-analysis.example.json`: example analysis output for a food/travel clip.

## Analyze Videos

Install dependencies:

```sh
uv sync
```

Run the VLM analysis script on a directory of videos:

```sh
uv run python scripts/analyze_video_twelvelabs.py assets/2026-05-02
```

Directory runs process clips in parallel with up to 10 workers by default. You can lower the cap if needed:

```sh
uv run python scripts/analyze_video_twelvelabs.py assets/2026-05-02 --max-concurrency 3
```

The script loads `TWELVELABS_API_KEY` from `.env`, skips videos shorter than TwelveLabs' 4 second minimum, uploads each remaining local video as a TwelveLabs asset, and writes normalized analysis plus raw TwelveLabs output to `cache/<time-sortable-run-uuid>/`. The normalized output contains a `clips` array. Each clip includes parsed capture time/location metadata when ffprobe can read it, plus timestamped `moments` with description, subjects, actions, visible text, spoken text, audio, quality, issues, and why the moment may be useful. Skipped videos are recorded in `raw-output.json` under `skippedClips`.

The TwelveLabs-specific logic lives in `scripts/twelvelabs_analyzer.py` behind an `analyze_video(video_path) -> (clip, raw_json)` interface. It handles asset upload/reuse, polling, provider schema, and normalization. Assets are deduped without local state by uploading with a deterministic filename based on `sha256(first 4MB + last 4MB + file size)`.

The normalized VLM output schema is defined with Pydantic models in `scripts/vlm_schema.py`.
