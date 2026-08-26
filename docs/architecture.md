# Architecture

## Canonical end-to-end flow

```
                AI CARTOON FACTORY

                     SERIES
                       │
             ┌─────────┴──────────┐
             │                    │
      Character Bible         Story Bible
             │                    │
             └─────────┬──────────┘
                       ▼
                  Episode Agent          (agents/story_agent.py)
                       │
                       ▼
                     Script              metadata/episode.json
                       │
                       ▼
                   Storyboard             agents/storyboard_agent.py
                       │
                       ▼
                 Scene Manifest           metadata/scene-manifest.json
                       │
      ┌────────────────┼────────────────┐
      ▼                ▼                ▼
   Stills            Voice            Music/SFX
 (image agent)    (audio agent)     (procedural/library)
      │                │
      ▼                │
 Image QC              │
      │                │
      ▼                │
 Motion Engine         │
 (KenBurns / Veo)      │
      │                │
      ▼                │
 Video QC              │
      └────────────────┼────────────────┘
                       ▼
                 Timeline Engine        assembly/timeline_engine.py
                       │
                       ▼
                 FFmpeg conform/concat/mix
                       │
                       ▼
                 Automated QC           qc/
                       │
                       ▼
                  Human Review          pipeline/gates.py (GATE 5)
                       │
                       ▼
                    MASTER.mp4 → publish-package/
```

## Source of Truth contracts

All shapes are pydantic models in `src/zkid/models/`, exported to `schemas/*.schema.json`:

| Contract | Model | Written by |
|---|---|---|
| series-bible | `SeriesBible` | templates / `zkid init-series` |
| character-bible | `CharacterSpec` | templates / Character Agent |
| episode | `EpisodeScript` | Story Agent |
| storyboard | `Storyboard` | Storyboard Agent |
| scene-manifest | `SceneManifest` | Manifest Generator |
| timeline | `EpisodeTimeline` | Timeline Engine |
| provenance | `AssetProvenance` | every generating agent |

Master character prompts are derived, never stored ad hoc: `CharacterSpec.master_prompt()`.
Scene/image/video prompts **append** to the master prompt.

## Render queue state machine

```
PENDING → GENERATING → VALIDATING → APPROVED
               │            │
               ▼            ├──→ RETRY → GENERATING ...
             FAILED ◄───────┴──→ MANUAL_REVIEW → APPROVED (human)
```

- Transitions constrained by `models/enums.py::ALLOWED_TRANSITIONS`
- Idempotency keys `{ep}:{scene}:{KIND}:v{n}` make network retries safe
- Retry ladder per blueprint: attempt 2 strengthens identity constraints,
  attempt 3 simplifies motion, then MANUAL_REVIEW (`pipeline/retry.py`)
- Budgets: images/videos/cost per episode (`pipeline/budget.py`), enforced before spend

## Timing model

- The Timeline Engine is the only place that computes timestamps.
- Scene duration = max(manifest duration, voice duration + padding).
- Scene videos shorter than the final slot are extended by last-frame clone
  (`assembly/ffmpeg.py::conform_clip`, tpad) — audio is never sped up.
- Music beds are planned per story segment (hook/playful/discovery/learning-song/ending)
  and ducked under dialogue via sidechain compression at mix time.

## Gates

| Gate | Meaning | Auto rules |
|---|---|---|
| GATE 1 | Story approved | auto in draft mode (configurable) |
| GATE 2 | Characters + storyboard approved | auto in draft mode |
| GATE 3 | Scene generation approved | system-qc approves iff all VIDEO jobs APPROVED |
| GATE 4 | Final video QC | system-qc approves iff automated QC passes |
| GATE 5 | Human publish approval | **never** automatic; explicit CLI override only |

## Persistence

SQLite (`factory.db`) via `db/database.py`: series, characters, episodes, scenes,
assets (+provenance JSON), voices, generation_jobs, renders, qc_results, gates,
publications. Repository API in `db/repo.py`.

## Provider adapters

`engines/base.py` defines ABCs; `engines/registry.py` selects from
`config/factory.yaml providers:` overridden by `ZKID_*_PROVIDER` env vars.

| Kind | Offline twin | Cloud adapter |
|---|---|---|
| LLM | deterministic story factory | OpenAI-compatible endpoint |
| image | FFmpeg gradient stills | Google Imagen |
| voice | timed silence (correct durations) | Gemini TTS |
| music/sfx | sine-bed procedural cues | licensed library (drop-in) |
| motion | Ken Burns zoompan | Veo 3.1 image-to-video |

Cloud adapters import their SDKs lazily and raise `EngineNotConfigured` when unconfigured,
so the offline path always works.
