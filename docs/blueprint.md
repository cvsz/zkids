# Production Blueprint (condensed)

Source document for this repository's design. Status: Production Blueprint.

## Core idea

Not mass image generation — a **Source of Truth** shared by every AI agent:

```
series-bible.json → character-bible.json → episode.json → storyboard.json
→ scene-manifest.json → timeline.json
```

Lock these contracts and providers can be swapped without redesigning the system.

## Six production principles

1. **Original IP** — own characters, names, worlds, music, story structures; never imitate
   Disney/Pixar/Peppa/Cocomelon properties.
2. **Character consistency** — one canonical Character Bible per character; scene prompts
   append to the master prompt, never replace it.
3. **Scene-based production** — every episode decomposes into scenes/shots (`S001…`);
   every asset binds back to a `scene_id`.
4. **Audio-driven timing** — voice dictates pacing; video adapts to audio, not vice versa.
5. **Automation with human QC** — machines generate/queue/retry/render; humans approve
   before publish, especially for kids' content.
6. **Quality over mass generation** — low-quality made-for-kids content risks limited
   monetization; differentiate on real value.

## Story formula

```
HOOK → SETUP → PROBLEM → DISCOVERY → TRY → SOLUTION → LEARNING RECAP → ENDING
```

Example 4-minute allocation: 0:00-0:15 hook · 0:15-0:45 setup · 0:45-1:30 problem ·
1:30-2:30 adventure · 2:30-3:20 solution · 3:20-3:50 recap · 3:50-4:00 ending.

## Master baseline

MP4 · H.264 · 1920×1080 · 30 FPS · AAC · 48 kHz stereo. Normalize resolution/fps/codec/
pixel format/audio rate on every asset before concatenation.

## Audio-first sync

If voice exceeds video: add B-roll → generate continuation → reaction shot → extend
scene → adjust script. Never heavily speed up speech to fit.

## Retry ladder

Attempt 2 strengthens character constraints; attempt 3 simplifies motion; then MANUAL
REVIEW. Always set max retries to prevent runaway spend.

## Idempotency & provenance

Every job carries an idempotency key (`EP001:S003:VIDEO:v4`) so network retries cannot
double-spend. Every asset records provider, model, prompt version, seed, references,
character version, approval state (`.prov.json` sidecars).

## Gates

GATE 1 story · GATE 2 characters/storyboard · GATE 3 scene generation · GATE 4 final QC ·
GATE 5 human publish approval (never auto-approved). Gates protect against wrong
generation at scale, unsafe content, character drift, runaway cost, accidental publishing.

## Made-for-Kids reality

Made-for-Kids content loses personalized ads, comments, notifications, cards/end screens;
contextual ads remain. Do not model kids-channel revenue with generic CPM/RPM. Optimize:
original IP + retention + repeat viewing + episode library + discovery + production cost.

## KPIs

- Content: CTR, avg view duration, % viewed, returning viewers, completion
- Production: cost/episode, cost/approved scene, retry rate, character failure rate,
  render failure rate, generation time
- Quality: character consistency %, audio/video QC pass %, manual intervention %
- Business: revenue/episode, revenue/1k views, break-even views, episode ROI

## Feedback loop

Publish → YouTube Analytics → retention analysis → scene drop-off detection
(dialogue too long? static scene? confusing beat?) → Story Agent improves next episode.
The factory is a learning loop, not just a generator.

## MVP definition of done (achieved in this repo)

Topic in → one complete episode out → no manual scene dragging in an editor.
