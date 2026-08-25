# zkids AI Kids Cartoon Factory — Architecture Specification

**Date:** 2026-08-26  
**Repository:** `cvsz/zkids`  
**Status:** Approved for implementation  
**Primary goal:** Turn an original, age-appropriate episode specification into a validated, provenance-aware, renderable production package while keeping human approval before publication.

## 1. Product boundary

`zkids` is a production control plane and media-pipeline foundation for original children's animation. It owns the canonical source of truth, orchestration state, provider boundaries, validation, quality gates, timeline assembly, cost controls, and publication readiness. It does not embed a specific commercial AI provider, bypass provider policy, or publish without an explicit approval state.

The first repository delivery includes three layers:

1. **Documentation and contracts:** bilingual product/architecture documentation and versioned JSON Schemas for series, characters, episodes, storyboards, scene manifests, timelines, asset provenance, jobs, QC, and publication.
2. **Runnable MVP core:** a Python package and CLI that validate contracts, plan scenes, enforce idempotency and retry/budget rules, build timelines, run deterministic QC, and produce a local production package.
3. **Production platform foundation:** a FastAPI control-plane surface, durable local repository implementations, worker/provider protocols, object-storage and queue extension points, structured events, Docker/CI foundations, and an explicit path to PostgreSQL/Redis/S3-compatible deployments.

Actual image, voice, music, video, and publishing integrations are adapters. The repository ships safe dry-run implementations and contracts; credentials and vendor-specific calls are configured outside source control.

## 2. Core workflow

The canonical workflow is:

```text
Idea → Story Bible → Character Bible → Script → Storyboard → Scene Manifest
     → Voice / Music / SFX → Still Image → Image QC → Motion Video → Video QC
     → Timeline → Audio Mix → Subtitles → Final QC → Human Approval → Publish
```

Every downstream artifact references stable IDs and versions. A scene is never rendered from an unconstrained prompt: provider prompts are compiled from the locked character/series contracts plus scene-specific instructions.

Workflow gates:

- `STORY_APPROVED`
- `CHARACTER_STORYBOARD_APPROVED`
- `SCENE_GENERATION_APPROVED`
- `FINAL_QC_APPROVED`
- `HUMAN_PUBLISH_APPROVED`

No transition can skip a required gate, and publication is denied unless the final gate is present.

## 3. Repository shape

```text
zkids/
├── docs/
│   ├── architecture.md
│   ├── production-blueprint.th.md
│   ├── production-blueprint.en.md
│   ├── operations.md
│   └── superpowers/specs/2026-08-26-zkids-design.md
├── schemas/
│   ├── series.schema.json
│   ├── character.schema.json
│   ├── episode.schema.json
│   ├── storyboard.schema.json
│   ├── scene-manifest.schema.json
│   ├── timeline.schema.json
│   ├── asset.schema.json
│   ├── generation-job.schema.json
│   ├── qc-result.schema.json
│   └── publication.schema.json
├── examples/episode-001/
│   ├── series.json
│   ├── characters/mimi.json
│   ├── episode.json
│   ├── storyboard.json
│   ├── scene-manifest.json
│   └── timeline.json
├── src/zkids/
│   ├── api/
│   ├── contracts/
│   ├── pipeline/
│   ├── providers/
│   ├── qc/
│   ├── render/
│   ├── storage/
│   └── cli.py
├── tests/
├── deploy/
│   ├── Dockerfile
│   └── docker-compose.yml
├── .github/workflows/ci.yml
├── pyproject.toml
└── README.md
```

## 4. Contract rules

- IDs are stable, opaque strings such as `SERIES-001`, `MIMI-001`, and `EP001-S003`.
- Durations and timestamps are decimal seconds; frame-rate conversion happens only in the renderer.
- Schemas use JSON Schema 2020-12 and reject unknown fields where a contract is locked.
- `scene_id` is the join key for stills, videos, voice, music cues, SFX, subtitles, QC, and provenance.
- `AssetProvenance` records provider, model, prompt version, character version, references, seed when available, timestamps, and approval state.
- `GenerationJob.idempotency_key` is required and unique for a logical generation request.
- Budget and retry ceilings are explicit on every generation job and episode.
- Provider responses are normalized into internal contracts before persistence.

## 5. Runtime architecture

The control plane exposes a narrow API for creating and validating production specifications, enqueueing jobs, reading job state, and approving gates. The pipeline engine consumes jobs through a queue port and delegates generation to provider ports. A local SQLite/JSON-compatible implementation makes the MVP runnable without cloud services; production deployments can substitute PostgreSQL, Redis, and S3-compatible object storage without changing domain contracts.

Provider ports:

- `StoryProvider`
- `CharacterProvider`
- `StoryboardProvider`
- `VoiceProvider`
- `MusicProvider`
- `ImageProvider`
- `MotionProvider`
- `RenderProvider`
- `PublishingProvider`

Each port has a deterministic dry-run implementation. A provider adapter must return the same internal contract regardless of vendor and must attach provenance before the asset becomes eligible for QC.

## 6. QC and safety

Deterministic checks run before any expensive downstream stage:

- contract/schema validation
- required asset and scene coverage
- character identity and immutable-field constraints
- timeline overlap/gap and duration checks
- media probe checks when FFmpeg is available
- subtitle bounds and spelling metadata checks
- provenance completeness
- budget, retry, and timeout checks
- publication readiness and human approval checks

Model-assisted visual or content checks are represented by a `QCProvider` port and cannot silently override a failed deterministic check. Content is designed for the declared age range, original-IP constraints, and human review. The system records an audit event for every approval, rejection, retry, and publication decision.

## 7. API and CLI surface

The initial control-plane API provides:

- `GET /healthz`
- `POST /v1/validate`
- `POST /v1/episodes`
- `GET /v1/episodes/{episode_id}`
- `POST /v1/jobs`
- `GET /v1/jobs/{job_id}`
- `POST /v1/episodes/{episode_id}/gates/{gate}`
- `POST /v1/render/plan`

The CLI mirrors the safe local path:

```text
zkids validate examples/episode-001
zkids plan examples/episode-001/timeline.json
zkids qc examples/episode-001
zkids package examples/episode-001 --output dist/episode-001
```

The CLI is offline-first. Live provider and publishing operations require explicit configuration and are not enabled by default.

## 8. Reliability and security

- Fail closed on invalid contracts, missing provenance, budget exhaustion, or missing approvals.
- Never log secrets, provider tokens, raw child personal data, or private media URLs.
- Validate paths before local artifact access; reject path traversal and symlink escapes.
- Treat prompts, scripts, filenames, and metadata as untrusted input at every boundary.
- Use structured JSON logs with correlation IDs and immutable audit events.
- Keep retries bounded and idempotent; no automatic infinite retry loops.
- Keep publication separate from rendering and require a human approval record.
- Pin development tooling and run dependency, static, unit, contract, and security checks in CI.

## 9. Delivery and evolution

The repository is intentionally provider-neutral and self-hostable. The MVP is complete when the sample episode can be validated, planned, QC-checked, and packaged without external credentials. Production readiness adds real provider adapters, PostgreSQL/Redis/S3 deployments, authentication/authorization, worker autoscaling, media probes, model-assisted QC, analytics ingestion, and provider-specific publishing integrations behind the same contracts.

This design keeps the source of truth stable while allowing providers, renderers, and deployment infrastructure to evolve independently.
