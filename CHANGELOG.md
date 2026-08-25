# Changelog

All notable changes to this project are documented here.

The format is based on Keep a Changelog and the project follows Semantic Versioning.

## [1.0.0] - 2026-08-26

### Added

- character registry/versioning persistence and tenant-scoped API
- storyboard revision API
- render job retry/cancel operator controls with audit events
- QC review persistence
- server-rendered tenant-scoped `/control` dashboard
- deterministic fake publishing boundary for CI/offline validation
- publication idempotency and replay protection
- analytics ingestion with event-id idempotency
- scene-level retention aggregation
- multilingual and experiment/creative episode variants
- PostgreSQL migration `0002_final_release.sql`
- P3/P4 regression tests for tenant scoping, analytics, variants and publication gating

### Changed

- package version advanced to `1.0.0`
- FastAPI application version advanced to `1.0.0`
- readiness diagnostics now expose release version and publishing configuration mode
- ROADMAP and EXEC-PLANNING mark P0 through P4 code-complete

### Security

- publication requires `approve_publish` permission and `HUMAN_PUBLISH_APPROVED` episode state
- `approved_by` must match the authenticated publishing actor
- provider and publishing credentials remain environment-only
- no paid media generation or external publishing call is required in CI
- all new metadata records are tenant-scoped

## [0.2.0]

### Added

- production provider adapter boundaries for image, voice, and motion/video generation
- S3-compatible object storage with local fallback and immutable content-addressed asset keys
- PostgreSQL production job and usage-event schema foundation
- Redis-compatible queue and worker entrypoint
- signed bearer authentication, RBAC, and tenant-scoped episode/job access
- provider cost metering integrated with bounded budget accounting
- production-like Docker Compose stack for API, worker, PostgreSQL, Redis, and MinIO
- P2 unit/security/container validation and fake-provider integration coverage

### Security

- provider secrets are read from environment variables only
- protected API surfaces enforce tenant boundaries when authentication is enabled
- publication remains fail-closed behind explicit human approval
- CI does not call paid external media providers

## [0.1.0]

### Added

- Repository template baseline
- Security and contribution policies
- GitHub issue and pull request templates
- CI, CodeQL, dependency review, and Dependabot automation
- Release workflow and project documentation structure
- Episode, Scene, and Generation Job state machines
- typed prompt compiler and provider capability negotiation
- asset lineage graph, deterministic QC policy, and budget accounting
- JSON Schema and Pydantic contracts
- SQLite persistence and append-only audit events
- dry-run provider, timeline compiler, FFmpeg probe path, CLI, and FastAPI control plane
- hardened Docker runtime and offline E2E validation path
