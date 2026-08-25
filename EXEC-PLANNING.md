# EXEC-PLANNING

## Baseline

Architecture baseline: `docs/superpowers/specs/2026-08-26-zkids-design.md` (approved 2026-08-26).

## Slice P0 — Core execution semantics

Status: COMPLETE / MERGED

Acceptance criteria:

1. Illegal Episode/Scene transitions fail closed.
2. Human publish approval is an explicit state before publication.
3. Motion provider requests are compiled from typed character and scene contracts.
4. Capability mismatches reject before expensive provider submission.
5. Asset lineage is acyclic and can identify descendants for invalidation.
6. Deterministic hard QC failures cannot be overridden by soft model scores.
7. Budget reservations are bounded and reject over-budget work.

## Slice P1 — Offline vertical slice

Status: IMPLEMENTED IN PR #6; merge only after all repository gates pass.

Delivered:

1. JSON Schema 2020-12 contracts for series, character, episode, storyboard, scene manifests, timelines, assets, jobs, QC, and publication.
2. Typed Pydantic domain models with unknown-field rejection.
3. SQLite episode/job repository plus append-only audit-event store.
4. Deterministic dry-run provider behavior with provenance output.
5. Idempotent generation-job creation through a unique logical idempotency key.
6. Timeline normalization/compiler with gap warnings and overlap rejection.
7. Safe FFmpeg/ffprobe capability detection and probe path.
8. CLI `validate`, `plan`, `qc`, `package`.
9. FastAPI health/validation/episode/job/gate/render/publication-readiness endpoints.
10. Hardened Docker runtime and Compose baseline.
11. Format, lint, strict typing, Bandit, pytest, existing CI, CodeQL, dependency review, and offline CLI E2E gates.
12. Sample `examples/episode-001` production package path requiring no external credentials.

## v0.1 release gate

`v0.1.0` is releasable only when the PR head is green for all configured CI/security checks. The offline E2E must prove:

```text
examples/episode-001
  -> validate
  -> deterministic timeline plan
  -> deterministic QC
  -> package-manifest.json
  -> READY_FOR_HUMAN_REVIEW
```

Publication remains denied until explicit human approval. Real paid provider integration is intentionally outside v0.1.

## Slice P2 — Production provider/infrastructure adapters

Next after v0.1:

1. Image and voice provider adapters.
2. Motion/video adapter behind `MotionProvider` and capability negotiation.
3. S3-compatible object storage and immutable asset addressing.
4. PostgreSQL repositories and Redis-compatible worker queue.
5. Authentication/RBAC and tenant boundaries.
6. Provider cost metering, durable retry telemetry, and worker leasing.
7. Model-assisted QC that cannot override deterministic hard failures.
8. Publishing adapters behind durable human approval.
9. Analytics ingestion and scene-level feedback loop.

## Rollback

P1 remains additive. Revert PR #6 to return to the P0 baseline; no external provider mutation, cloud resource, or production database migration is introduced by v0.1.
