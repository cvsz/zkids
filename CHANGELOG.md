# Changelog

All notable changes to `zkids` are documented here.

The project follows Keep a Changelog principles and Semantic Versioning where practical.

## [Unreleased]

### Added

- Production-oriented repository governance, CI, CodeQL, dependency review, and Dependabot automation.
- P0 state machines, prompt compiler contracts, provider capability negotiation, asset lineage, QC policy, and budget controls.
- P1 JSON Schema 2020-12 contract set and typed Pydantic models.
- SQLite episode/job persistence with unique idempotency keys and append-only audit events.
- Deterministic dry-run provider and offline sample episode.
- Timeline overlap/gap validation and safe FFmpeg/ffprobe probing.
- CLI commands: `validate`, `plan`, `qc`, and `package`.
- Minimal FastAPI control plane for validation, episodes, jobs, approval gates, render planning, and publication readiness.
- Hardened Python Docker runtime and local Docker Compose baseline.
- Python format/lint/type/security/test and offline CLI E2E workflow.

### Changed

- Replaced the generic placeholder Dockerfile with the non-root `zkids` API runtime.
- Reframed the repository from a generic template baseline into the `zkids` offline-first production control plane.

### Fixed

- Typed state-transition validation now preserves concrete Episode/Scene state types under strict mypy.
- FFprobe invocation resolves the executable path before process execution.

### Security

- Publication remains fail-closed without explicit human approval.
- Local artifact resolution rejects path traversal and root escapes.
- Provider credentials and live paid-provider calls remain outside the v0.1 offline slice.
- Security scans retain their thresholds; narrowly scoped Bandit annotations document non-secret QC tokens and fixed-shell-free FFprobe execution.
