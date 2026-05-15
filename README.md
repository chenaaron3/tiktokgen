# AI Shorts Editor

Local CLI-first MVP for turning food and travel clips into 30-45 second vertical aesthetic b-roll shorts.

## Documents

- `docs/product-spec.md`: MVP product spec.
- `docs/vlm-schema-prototype.md`: rationale and validation plan for the VLM output schema.
- `docs/creative-contract.md`: creative rules for selecting and sequencing footage.

## Prototype Artifacts

- `schemas/edit-plan.schema.json`: legacy Remotion plan (superseded by `render-plan.json` from `scripts/edit`).
- `scripts/vlm/schema.py`: Pydantic models for VLM analysis JSON (`model_json_schema()`, `model_validate()`).

## Python Modules

Shared Python code is grouped under `scripts/`:

- `scripts/vlm/`: VLM analysis, media probing, TwelveLabs provider, and VLM schema exports.
- `scripts/edit/`: `shot-match.json` (LLM) and deterministic `render-plan.json`.
- `scripts/narrative/`: script LLM, ElevenLabs TTS, faster-whisper word timings, sentence ledger.
- `scripts/contracts.py`: shared sentence/token DTOs.
- `scripts/project_inputs.py`: repo-root path helpers, bundled **Project** resolution (`resolve_bundled_project`, `notes.yaml`).
- `scripts/util/path_util.py`: run artifact paths (`PathUtil`, `RunStage` registry).
- `scripts/util/artifact_cache.py`: shared Pydantic JSON read/write for stage artifacts.
- `scripts/fixtures/pipeline.py`: sample words + sample `ShotMatch` for tests.
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

Run the **narrative pipeline** (script → TTS → Whisper → VLM → shot-match LLM → deterministic `render-plan.json` → Remotion).

**SOURCE** is always a **project folder**: your video clips and **`notes.txt`** (exact filename) in the **same directory** (for example `assets/05-03`).

**Fixed run id** (folder name only, resolved as `--cache-dir`/`<run-id>`):

```sh
PYTHONPATH=scripts uv run python scripts/run_pipeline.py assets/05-03 \
  --run-id 019e0648-d859-79d1-bd1c-dcf5e431e360
```

**Default cache run** (new UUID under `--cache-dir` when you omit `--run-id` / `--resume`):

```sh
PYTHONPATH=scripts uv run python scripts/run_pipeline.py assets/05-03
```

**Resume latest run:** reuse the subdirectory of `--cache-dir` that was modified most recently (do not combine with `--run-id`):

```sh
PYTHONPATH=scripts uv run python scripts/run_pipeline.py assets/05-03 \
  --resume
```

Artifacts land under `cache/<run-id>/` (chosen explicitly, new UUID, or resumed folder): `script.txt`, `voiceover.mp3`, etc. (see below).

Env vars: `TWELVELABS_API_KEY`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`. Optional override: `ELEVENLABS_VOICE_ID` (defaults to the same ElevenLabs voice id as shortgen: `NFG5qt843uXKj4pFvR7C`).

The VLM stage needs **ffmpeg** when a clip is under TwelveLabs' ~4s minimum: those files are lengthened using a freeze-frame/audio-pad tail, then analyzed; **outputs still reference your original paths and durations.** Each clip payload is the restaurant `identified_shots` taxonomy (`scripts/vlm/schema.py`).

Shot matching is a **single LiteLLM JSON call** producing reviewable `shot-match.json`. Assembly is deterministic and writes `render-plan.json` (beats w/ `playbackRate`, voice static path, Whisper word captions). Logs under `llm-observability/`.

**Unit tests:** `uv sync --group dev` then `uv run pytest`.

Service calls are behind **protocols** (`narrative.providers`, `edit.providers`, `vlm.providers`) so tests can inject mocks.

Open the Remotion Studio/editor:

```sh
npm run dev
```

Render manually (the harness already invokes this after copying media into `remotion/public/`):

```sh
npm run render -- cache/<run-id>/render.mp4 --props "$(python -c 'from pathlib import Path; print(Path("cache/<run-id>/render-plan.json").read_text())')"
```

Remotion composition `AiShort` reads `render-plan.json` (voice + beats + word captions).

To continue a specific run, pass **`--run-id`** with the folder name under **`--cache-dir`** (for example the UUID). Existing files skip their stages (for example cached `vlm-analysis.json`, `shot-match.json`, `voiceover.mp3`).

Alternatively use **`--resume`** instead of **`--run-id`** to reuse the newest run folder under **`--cache-dir`** (see above).
