# ROADMAP

## v0.1 — Offline-first core foundation

- [x] Domain state machines and fail-closed transitions
- [x] Typed prompt compiler contracts
- [x] Provider capability negotiation
- [x] Asset lineage DAG
- [x] Hard/soft QC decision policy
- [x] Budget accounting primitive
- [x] Versioned JSON Schemas
- [x] SQLite/local durable repositories
- [x] Deterministic dry-run providers
- [x] Scene planner and timeline compiler
- [x] FFmpeg/ffprobe safe path
- [x] CLI validate / plan / qc / package
- [x] Minimal FastAPI control plane
- [x] Immutable audit events
- [x] Docker/local compose
- [x] lint/type/security/test/offline-E2E CI

## v0.2 — Production provider/infrastructure adapters

- [x] Image / voice / motion provider boundaries
- [x] S3-compatible object storage
- [x] PostgreSQL repository/migrations
- [x] Redis worker queue
- [x] Authentication/RBAC/tenant boundaries
- [x] Cost metering/retry primitives
- [x] Environment-only provider credentials
- [x] Production Compose stack
- [x] Security/unit/container CI

## v0.3 — Product control plane

- [x] Character library and versioning API/UI surface
- [x] Storyboard/scene revision editor API
- [x] Render job monitor with retry/cancel operations
- [x] QC review surface/API
- [x] Human approval and publication control surface
- [x] Tenant-scoped dashboard

## v0.4 — Publishing and optimization

- [x] Publishing boundary behind explicit HUMAN_PUBLISH_APPROVED gate
- [x] Deterministic fake publisher for offline/CI validation
- [x] Publication idempotency/replay protection
- [x] Analytics ingestion
- [x] Scene-level retention attribution
- [x] Multi-language episode variants
- [x] Experiment/creative variant model
- [x] PostgreSQL final-release migration

## v1.0 — Final Release

- [x] P0–P4 code-complete
- [x] Offline-first path preserved
- [x] Human publication remains fail-closed
- [x] Tenant/RBAC boundaries preserved
- [x] No provider credentials persisted
- [x] No paid provider calls required in CI
- [x] Release test coverage for control plane, analytics, variants and publishing

### Production activation boundary

`v1.0` is code-complete. Real external publishing or paid media generation still requires operator-owned provider credentials/accounts and explicit environment configuration. Those external account authorizations are deployment prerequisites, not repository code gaps.
