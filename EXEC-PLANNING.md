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

Status: COMPLETE / MERGED IN PR #6

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

## Slice P2 — Production provider/infrastructure adapters

Status: IMPLEMENTED ON `feat/p2-production-adapters`; merge only after all repository gates pass.

Delivered:

1. Vendor-neutral HTTP production adapter boundary for image, voice, and motion/video generation.
2. Motion request shape supports image input, reference assets, duration, aspect ratio, and resolution while retaining existing capability negotiation.
3. Environment-only provider credentials; no provider secret is accepted in persisted job payloads.
4. `LocalObjectStore` plus optional S3-compatible object storage and immutable SHA-256 asset keys.
5. PostgreSQL production-job/usage-event repository foundation plus versioned SQL migration.
6. Redis-compatible durable queue and a worker entrypoint for leased jobs.
7. Signed bearer-token authentication, role-based permissions, tenant claims, tenant-scoped episode/job reads, and explicit publisher permission for human publish approval.
8. Cost metering around provider execution with existing budget accounting as the fail-closed spend limit.
9. Deterministic fake provider path for CI and integration tests; CI performs no paid provider request.
10. Production-like Compose stack: API, worker, PostgreSQL, Redis, and MinIO.
11. `/readyz` and `/v1/auth/whoami` control-plane diagnostics.
12. P2 tests for RBAC, tenant claims, immutable storage keys, cost/budget enforcement, motion request mapping, and retry backoff.
13. CI expansion to production extras, Docker image build, and Compose validation.

## v0.2 release gate

P2 is releasable only when:

- existing v0.1 offline E2E remains green;
- P2 format/lint/mypy/Bandit/pytest pass;
- repository CI, CodeQL, and dependency review pass;
- Docker build and Compose validation pass;
- authentication remains opt-in for offline development but is enabled whenever `ZKIDS_AUTH_SECRET` is set;
- human publish approval remains fail-closed and requires `approve_publish` permission;
- provider credentials come from environment variables only;
- CI uses only fake/local providers and performs no paid external generation calls.

## Next after P2

P3 / v0.3 is the product control plane: character versioning, storyboard editor, render monitor/retry surface, QC review, and human approval UI. Publishing adapters and analytics feedback remain v0.4 scope.

## Rollback

P2 is additive to the P1 contracts. Revert the P2 merge commit to return to the v0.1 offline baseline. The repository does not automatically provision or mutate external provider accounts; PostgreSQL/Redis/S3 adapters require explicit operator configuration.
