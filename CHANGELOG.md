# Changelog

All notable changes to this project are documented here.

The format is based on Keep a Changelog and the project follows Semantic Versioning.

## [Unreleased]

### Added

- v0.2 production provider adapter boundaries for image, voice, and motion/video generation
- S3-compatible object storage with local fallback and immutable content-addressed asset keys
- PostgreSQL production job and usage-event schema foundation
- Redis-compatible queue and worker entrypoint
- signed bearer authentication, RBAC, and tenant-scoped episode/job access
- provider cost metering integrated with bounded budget accounting
- production-like Docker Compose stack for API, worker, PostgreSQL, Redis, and MinIO
- P2 unit/security/container validation and fake-provider integration coverage

### Changed

- package version advanced to `0.2.0`
- Python CI now installs production extras and validates P2 files, Docker image build, and Compose configuration
- API reports readiness/auth configuration and enforces `approve_publish` permission when authenticated

### Fixed

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
