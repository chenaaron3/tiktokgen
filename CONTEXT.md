# AI Shorts Editor

A local pipeline that turns food-and-travel footage into short-form vertical videos. Creators supply raw media and notes; the system analyzes footage, drafts an edit, and renders a polished short.

## Language

**Project**:
The user's input bundle: a folder of source videos plus notes (`notes.yaml`).
_Avoid_: Using "project" for the cache/output tree.

**Notes**:
The creator-authored brief bundled with a project — place, dishes, opinions, must-use intent.
_Avoid_: Metadata, brief, context file.

**Script**:
The full generated narration text before speech timing is resolved.
_Avoid_: Voiceover (the synthesized audio artifact).

**Voiceover**:
The synthesized narration audio track for a short.
_Avoid_: TTS output, voice, audio file.

**Sentence**:
One spoken narration line in the short, with resolved start and end time on the voiceover track.
_Avoid_: Line, phrase; caption (on-screen text is separate).

**Hook**:
The first sentence of the short — written and cut to grab the viewer immediately.
_Avoid_: Intro, opener, thumbnail moment.

**Caption**:
On-screen text timed to the voiceover — typically word-by-word over the short.
_Avoid_: Subtitle (full transcript).

**Overlay**:
On-screen text or graphics not tied word-for-word to the voiceover — e.g. hook title, location label.
_Avoid_: Caption (timed to speech); lower third.

**Shot match**:
The minimal, reviewable editorial assignment — which shots serve each sentence and how many beats each pick spans.
_Avoid_: Edit plan (legacy); cut list, timeline.

**Render plan**:
The fully resolved specification Remotion uses to render the short — every beat's source window and placement on the timeline.
_Avoid_: Edit plan (ambiguous with shot match).

**Run**:
One pipeline execution's artifact tree for a given project (analysis, editorial JSON, render output under `cache/`).
_Avoid_: Build, session, cache folder.

**Analysis**:
The trusted structured read of a **Project**'s **Clips** — which **Shots** exist, what they depict, and dish linkage — produced only after the VLM phase passes quality gates.
_Avoid_: VLM output, clip analysis, tagging; treating unverified provider output as **Analysis**.

**Clip**:
One source video file in a project — raw footage, typically 10–60 seconds, analyzed independently by the VLM.
_Avoid_: Video, file, asset (too generic); moment (editorial segment, not source media).

**Beat**:
A unit of time on the short's timeline — the rhythmic measure the edit is paced to. Beats will eventually be resolved from music so **B-roll** cuts can land on the track.
_Avoid_: Shot (source-side); cut, scene.

**Shot**:
A segment within a **Clip** — bounded time range with verified editorial metadata (tag, key instant, optional dish linkage, reasoning).
_Avoid_: Moment (creative-contract alias); scene, take.

**Shot label**:
The taxonomy tag and dish linkage on a **Shot** once it is trusted for **Analysis**.
_Avoid_: Raw provider metadata, unverified tag.

**Label confidence**:
TwelveLabs' certainty tier for an initial **Shot label** — `low`, `medium`, or `high` — before verification.
_Avoid_: Score, probability, percentage.

**A-roll**:
Primary footage where the subject or narrator carries the story — typically talking head or direct-to-camera.
_Avoid_: B-roll, voiceover (audio-only narration is not A-roll).

**B-roll**:
Supplementary visuals cut to illustrate the voiceover — food, place, ambience, detail.
_Avoid_: Stock footage, background video, filler; A-roll (this product does not use talking-head footage).

**Short**:
The rendered output video — vertical 9:16, typically 30–45 seconds, intended for Reels or TikTok.
_Avoid_: Video (too generic); render, output, final MP4.

## Relationships

- A **Project** contains one or more **Clips** and **Notes**.
- A **Run** produces **Analysis** of the project's clips (verified before downstream stages run).
- **Shot match** draws on **Analysis** only — it does not call the VLM again to recover labeling mistakes.
- A **Clip** contains one or more **Shots** (from VLM analysis).
- A **Script** becomes a **Voiceover**, then aligned **Sentences**; the first sentence is the **Hook**.
- Each **Sentence** claims a number of **Beats** on the short timeline.
- A **Short** is made of an ordered sequence of **Beats**.
- A selected **Shot** may span one or many **Beats** when used as **B-roll** in the short.
- Each **Sentence** is illustrated by **B-roll** — **Shots** chosen to fill that sentence's **Beats**.
- A **Short** pairs **Voiceover** with **B-roll**; this product edits **B-roll** only (no **A-roll** / talking heads).
- A **Shot match** is assembled into a **Render plan**; the **Render plan** drives production of the **Short**.
- A **Render plan** includes **Captions** timed to the **Voiceover** and **Overlays** (e.g. hook title).
- A **Project** may have one or more **Runs** over time (reruns, resumes).
- A **Run** belongs to exactly one **Project** (keyed by the project's source folder).
- A completed **Run** produces one **Short**.

## Example dialogue

> **Dev:** "If I edit `shot-match.json` and rerun assembly, do I need a new project?"
> **Domain expert:** "No — same **Project**, same or updated **Run**. You're re-executing stages on the existing run's artifacts."
>
> **Dev:** "Does the VLM analyze the whole project at once?"
> **Domain expert:** "It analyzes each **Clip** separately, then the editor works from those per-clip results."
>
> **Dev:** "Is the short the same thing as the project folder?"
> **Domain expert:** "No — the **Project** is input footage. The **Short** is what you publish, produced by a **Run**."
>
> **Dev:** "Why not just cut straight from shots to the final video?"
> **Domain expert:** "Shots live on source clips. **Beats** live on the short — they're how we measure pacing. Today that's driven by narration timing; later we'll resolve beats from music so **B-roll** lands on the track."
>
> **Dev:** "Is b-roll the same as a shot?"
> **Domain expert:** "A **Shot** is on the source clip. **B-roll** is what you see in the finished **Short** — shots selected and cut to fill beats under the **Voiceover**."
>
> **Dev:** "Do we ever cut to the creator talking?"
> **Domain expert:** "Not in this product. Narration is **Voiceover** only; all visuals are **B-roll**. **A-roll** isn't in scope."
>
> **Dev:** "How does the script relate to beats?"
> **Domain expert:** "The **Script** becomes timed **Sentences**. Each sentence gets a beat count from how long it plays — then we pick shots to fill those beats."

## Flagged ambiguities

- Product spec used "project" for both input folder and artifact storage — resolved: **Project** = input, **Run** = output.
- Creative contract uses "moment" for VLM-identified segments — resolved: canonical term is **Shot**.
- Product spec uses "edit plan" for both shot match and render plan — resolved: **Shot match** (minimal, editable) vs **Render plan** (resolved, for Remotion).
- **A-roll** / **B-roll** industry terms — resolved: this product produces **B-roll** shorts with **Voiceover**; **A-roll** is defined for contrast but out of scope.
- Unverified TwelveLabs labels vs downstream trust — resolved: pay the cost in the VLM phase; **Shot match** must not use ad-hoc VLM queries to fix bad labels.
- What “reliable VLM” guarantees — resolved: every **Shot** in **Analysis** has a verified **Shot label** (taxonomy tag and `dishName` when applicable).
- When GPT re-verifies a shot — resolved: **Label confidence** `low` or `medium` escalates to GPT; `high` is accepted into **Analysis** when schema-valid.
