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
- `scripts/edit/`: `shot-match.json` (LLM / review) and deterministic `render-plan.json`.
- `scripts/narrative/`: script LLM, ElevenLabs TTS, faster-whisper word timings, sentence ledger.
- `scripts/contracts.py`: shared sentence/token DTOs.
- `scripts/project_inputs.py`: bundled folder resolution (clips + `notes.txt` / lone `.txt`).
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

**Explicit run folder:**

```sh
PYTHONPATH=scripts uv run python scripts/render_short.py path/to/footage \
  --run-dir cache/my-run \
  --notes-file notes.txt \
  --auto-approve-script \
  --guidance "stylish West Village pacing"
```

**Project folder** (videos + notes in the **same directory** — e.g. `assets/05-03`): omit `--notes-file`. Prefer `notes.txt`, otherwise exactly **one** non-readme story `*.txt`.

```sh
PYTHONPATH=scripts uv run python scripts/render_short.py assets/05-03 \
  --auto-approve-script
```

**New UUID run** (`--cache-dir/<uuid>/` when you omit `--run-dir` / `--resume`): by default SOURCE is analyzed as footage only—still pass **`--notes-file`** unless SOURCE is the bundled **project folder** pattern above:

```sh
PYTHONPATH=scripts uv run python scripts/render_short.py path/to/clips-folder \
  --notes-file ./notes.txt \
  --auto-approve-script
```

**Resume latest run:** reuse the subdirectory of `--cache-dir` that was modified most recently (do not combine with `--run-dir`):

```sh
PYTHONPATH=scripts uv run python scripts/render_short.py path/to/footage \
  --resume \
  --auto-approve-script
```

Artifacts land under your chosen `--run-dir` or under `cache/<uuid>/` / the resumed folder (`script.txt`, `voiceover.mp3`, etc.; see below).

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

To continue a fixed run folder, pass **`--run-dir`**. Existing files skip their stages (for example cached `vlm-analysis.json`, `shot-match.json`, `voiceover.mp3`).

Alternatively use **`--resume`** instead of **`--run-dir`** to reuse the newest run folder under **`--cache-dir`** (see above).
