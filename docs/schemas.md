# Contracts (Schemas)

Single source of truth lives in `src/zkid/models/`. JSON Schemas are generated:

```bash
zkid export-schemas --out schemas
```

Regenerate and commit whenever a model changes.

| File | Model | Notes |
|---|---|---|
| `schemas/series-bible.schema.json` | `SeriesBible` | series identity, audience, visual style |
| `schemas/character-bible.schema.json` | `CharacterSpec` | canonical look, locked traits, voice profile, `master_prompt()` derivation |
| `schemas/episode.schema.json` | `EpisodeScript` | scenes with dialogue/action/camera/sfx cues |
| `schemas/storyboard.schema.json` | `Storyboard` | shots incl. reusable reaction/transition types |
| `schemas/scene-manifest.schema.json` | `SceneManifest` | render units: refs, environment, camera, motion, negatives |
| `schemas/timeline.schema.json` | `EpisodeTimeline` | video/voice/music/sfx/subtitle tracks with computed timestamps |
| `schemas/provenance.schema.json` | `AssetProvenance` | generator, model, seed, prompt, approvals per asset |
| `schemas/generation-job.schema.json` | `GenerationJob` | queue record incl. idempotency key + attempts |
| `schemas/live-character-prompt.schema.json` | `LiveCharacterPrompt` | real-time interactive avatar prompt: identity locks, live state machine, latency/streaming targets, voice prosody, response contract, memory + safety policy (instance: `templates/characters/NEKO-001-LIVE.json`) |

Rules of engagement:

1. Agents only exchange these models (JSON on disk + rows in SQLite).
2. IDs are stable: `MIMI-001`, `EP001`, `S003`, shots `{scene}-{TYPE}`, jobs
   `{ep}:{scene}:{KIND}:v{n}`, assets `KIND-{ep}-{scene}-v{n}`.
3. Timestamps appear only inside `EpisodeTimeline`.
4. Provenance sidecar files sit next to assets as `<file>.prov.json`.
