# EXEC-PLANNING

## Baseline

Architecture baseline: `docs/superpowers/specs/2026-08-26-zkids-design.md`.

## P0 — Core execution semantics

Status: COMPLETE / MERGED

- Fail-closed Episode/Scene transitions
- Explicit human publication approval state
- Typed prompt/provider contracts and capability negotiation
- Asset lineage, deterministic QC and bounded budget accounting

## P1 — Offline vertical slice

Status: COMPLETE / MERGED IN PR #6

- JSON Schema/Pydantic contracts
- SQLite durable repository + audit events
- Deterministic dry-run providers
- Timeline compiler + FFmpeg safety boundary
- CLI and FastAPI baseline
- Docker and offline E2E validation

## P2 — Production provider/infrastructure adapters

Status: COMPLETE / MERGED IN PR #7

- Image / voice / motion provider boundaries
- S3-compatible storage, PostgreSQL foundation, Redis worker queue
- RBAC + tenant boundaries
- Cost metering and retry primitives
- API / worker / PostgreSQL / Redis / MinIO Compose stack
- Production extras, Docker and Compose CI gates

## P3 — Product control plane

Status: IMPLEMENTED IN FINAL-RELEASE SLICE

Delivered:

1. Character registry/versioning persistence and tenant-scoped API.
2. Storyboard revision persistence and episode-bound editor API.
3. Render-job operator controls for retry/cancel with audit events.
4. QC review persistence with deterministic decision vocabulary.
5. Human approval and publication control surface.
6. Server-rendered `/control` dashboard with no additional frontend runtime dependency.
7. Existing RBAC and tenant boundaries enforced on all new API surfaces.

## P4 — Publishing and optimization

Status: IMPLEMENTED IN FINAL-RELEASE SLICE

Delivered:

1. Publication operation remains impossible before `HUMAN_PUBLISH_APPROVED`.
2. Authenticated `approved_by` actor binding.
3. Deterministic fake publisher for CI/offline validation.
4. Per-tenant publication idempotency/replay protection.
5. Analytics event ingestion with event-id idempotency.
6. Scene-level retention aggregation.
7. Multi-language episode variant records.
8. Experiment/creative variant association.
9. PostgreSQL migration for P3/P4 metadata.

## v1.0 release gates

The final release may merge only when:

- Ruff format/lint pass;
- strict mypy passes;
- Bandit passes;
- full pytest suite passes including P3/P4 tests;
- existing offline CLI E2E remains green;
- Docker build and production Compose validation pass;
- repository CI, CodeQL and dependency review pass;
- no real provider secret or credential is committed;
- CI performs no paid external provider or publishing calls;
- tenant isolation remains fail closed;
- publication requires publisher permission plus `HUMAN_PUBLISH_APPROVED` state;
- publication retries reuse the original external publication identity.

## Production activation

Code completion is independent from external account provisioning. Real Veo/image/TTS/music/publishing providers require operator-owned credentials, provider account authorization and environment configuration. The repository must not create, rotate or persist those secrets automatically.

## Rollback

The final-release slice is additive. Revert its merge commit to return to the v0.2 baseline. Database migration `0002_final_release.sql` only creates P3/P4 metadata tables and indexes; rollback can stop new writes and archive/drop those tables after data export if required.
