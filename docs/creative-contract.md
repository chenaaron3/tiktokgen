# Creative Contract

## Purpose

This contract defines what the MVP should consider a good food/travel short. It gives the future orchestrator a practical target before a full editing engine exists.

The MVP should produce aesthetic b-roll shorts that feel native to TikTok and Instagram Reels: fast, visual, polished, and easy to understand without requiring a complex story.

## Default Creative Brief

- Platform: TikTok and Instagram Reels.
- Format: vertical 9:16, 1080x1920.
- Duration: 30-45 seconds.
- Style: aesthetic b-roll.
- Pace: high-energy, with frequent cuts.
- Audio: usable without voiceover; optional TTS voiceover.
- Text: punchy overlays or captions, not dense subtitles by default.
- User control: editable JSON artifacts before render.

## Editing Priorities

The orchestrator should prefer:

1. Visually polished moments.
2. High-energy motion or strong visual rhythm.
3. Clear food/travel signals.
4. Variety across close-ups, ambience, details, and transitions.
5. Short, confident clips over long uncertain clips.

The orchestrator should avoid:

- Long static shots unless they are visually exceptional.
- Shaky footage held for more than a short transition.
- Repeated shots of the same subject unless the sequence improves rhythm.
- Ambiguous footage that requires context but has no clarification answer.
- Captions that explain more than the visuals can support.

## Draft Structure

The default draft should follow a simple visual rhythm:

1. Hook: strongest visual or most context-rich moment, usually 1.5-3 seconds.
2. Setup: location, ambience, or travel context, usually 2-5 seconds.
3. Main b-roll sequence: best food, place, activity, and detail shots.
4. Texture: quick ambience, people, movement, or transition shots.
5. Ending: satisfying final shot or visual button.

This is a loose structure, not a required narrative arc. A great aesthetic montage is acceptable even if it does not tell a full story.

## Moment Selection Rules

For 30-45 seconds of output, the edit plan should usually select 12-24 moments. Individual moments should commonly be 1-3 seconds, with occasional 3-5 second holds for exceptional visuals.

Strong moment candidates usually have:

- `quality` of `great` or `good`.
- Clear subjects.
- Visible action, motion, reveal, or atmosphere.
- Useful context from `description`, `subjects`, `actions`, `visibleText`, `spokenText`, or `audio`.
- Few or no serious `issues`.
- A convincing `whyUseful` note.

`okay` moments can be used when they provide important context, but they should usually be short. `poor` moments should be avoided unless the user explicitly marks them as important later.

## Voiceover Policy

Voiceover is optional in the MVP. The system should first generate a visual edit that works without TTS. If voiceover is enabled, the narration should add context, not describe every shot literally.

Good voiceover should be:

- Casual and UGC-friendly.
- Short enough to leave room for visual pacing.
- Focused on taste, feeling, place, or recommendation.
- Easy to skip without breaking the video.

Bad voiceover:

- Over-explains every visual.
- Sounds like a travel brochure.
- Forces a story that the footage does not support.
- Requires precise facts the system has not confirmed.

## Caption And Overlay Policy

Captions and overlays should support the aesthetic edit. The MVP should prefer short text moments such as:

- Location or place name.
- Dish/activity label.
- One-line reaction.
- Short recommendation.
- Light narrative beat.

Avoid dense subtitles unless they correspond to generated voiceover or meaningful original speech.

## Clarification Policy

The system should ask questions before render only when the answer would materially improve the edit. It should not block on trivial uncertainty.

Ask when:

- Location or place identity matters for the hook or captions.
- The system cannot tell whether the short should be food, travel, or mixed.
- TTS voiceover is requested but the system lacks enough context.
- There are multiple plausible themes with different edit outcomes.
- Must-use or must-avoid clips are unclear.

Do not ask when:

- The edit can proceed as an aesthetic montage.
- The uncertainty only affects optional metadata.
- The model has enough confidence to produce a reasonable draft.

## Editable Artifact Requirements

Every major decision should be represented in editable JSON before render:

- Which source clips are used.
- Start and end timestamps.
- Moment order.
- Intended duration.
- Crop/framing behavior.
- Overlay or caption text.
- Optional voiceover lines.
- Any assumptions or unresolved warnings.

The user should be able to edit these artifacts and rerun rendering without repeating VLM analysis.

## Acceptance Checklist

A first draft satisfies the creative contract when:

- It is 30-45 seconds long.
- It is vertical 9:16.
- It opens with a strong visual hook.
- It uses mostly high-quality, high-energy footage.
- It has enough variety to avoid feeling repetitive.
- It can be understood as a food/travel short without a long explanation.
- It does not depend on TTS to make basic sense.
- Captions or overlays are short and tasteful.
- Manual improvements can be made by editing JSON artifacts.

## Failure Cases

The draft should be considered unsuccessful if:

- It feels like a random slideshow.
- It includes long dull sections.
- It chooses visually weak moments when better options exist.
- It repeats similar shots without rhythm.
- It renders text that is unsupported or likely incorrect.
- It requires the user to rerun expensive analysis for simple edits.
