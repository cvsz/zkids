# ROADMAP

## v0.1 — Offline-first core foundation

- [x] Domain state machines and fail-closed transitions
- [x] Typed prompt compiler contracts
- [x] Provider capability negotiation
- [x] Asset lineage DAG
- [x] Hard/soft QC decision policy
- [x] Budget accounting primitive
- [x] Versioned JSON Schemas for series/character/episode/storyboard/scene/timeline/assets/jobs/QC/publication
- [x] SQLite/local durable repositories
- [x] Deterministic dry-run providers
- [x] Scene planner and timeline compiler
- [x] FFmpeg/ffprobe capability detection and safe probe path
- [x] CLI: validate / plan / qc / package
- [x] Minimal FastAPI control plane
- [x] Structured immutable audit events
- [x] Docker runtime and local compose baseline
- [x] Python lint/type/security/test/offline-E2E CI
- [x] Offline end-to-end production-package test path

### v0.1 exit criteria

`examples/episode-001` must validate, plan, pass deterministic QC, and package without external credentials or paid provider calls. Publication remains fail-closed until explicit human approval.

## v0.2 — Production provider/infrastructure adapters

- [x] Image provider adapter boundary
- [x] Voice provider adapter boundary
- [x] Motion/video provider adapter boundary with reference/duration/aspect/resolution payloads
- [x] S3-compatible object storage with local fallback and content-addressed keys
- [x] PostgreSQL repository/migration foundation
- [x] Redis-compatible worker queue and worker entrypoint
- [x] Authentication/RBAC and tenant boundaries
- [x] Provider-specific cost metering and production retry primitives
- [x] Environment-only provider credentials
- [x] Production-like Compose stack: API / worker / PostgreSQL / Redis / MinIO
- [x] P2 security/unit/container validation in CI

### v0.2 exit criteria

P2 must preserve the v0.1 offline path, perform no paid provider calls in CI, enforce tenant-scoped authorization when `ZKIDS_AUTH_SECRET` is configured, keep secrets out of persisted payloads, and preserve explicit human publish approval as a mandatory state/gate.

## v0.3 — Product control plane

- [ ] Character library and versioning UI
- [ ] Storyboard/scene editor
- [ ] Render monitor and retry UI
- [ ] QC review surface
- [ ] Human approval UI

## v0.4 — Publishing and optimization

- [ ] Publishing adapters behind explicit human approval
- [ ] Analytics ingestion
- [ ] Scene-level retention attribution
- [ ] Multi-language episode variants
- [ ] Experiment/creative variant model
