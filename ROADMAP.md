# ROADMAP

## v0.1 — Offline-first core foundation

- [x] Domain state machines and fail-closed transitions
- [x] Typed prompt compiler contracts
- [x] Provider capability negotiation
- [x] Asset lineage DAG
- [x] Hard/soft QC decision policy
- [x] Budget accounting primitive
- [ ] Versioned JSON Schemas for series/character/episode/storyboard/scene/timeline/assets/jobs/QC/publication
- [ ] SQLite/local durable repositories
- [ ] Deterministic dry-run providers
- [ ] Scene planner and timeline compiler
- [ ] FFmpeg probe/render adapter
- [ ] CLI: validate / plan / qc / package
- [ ] Minimal FastAPI control plane
- [ ] Structured audit events
- [ ] Offline end-to-end production-package test

## v0.2 — Real provider adapters

- [ ] Image provider adapter
- [ ] Voice provider adapter
- [ ] Motion/video provider adapter
- [ ] S3-compatible object storage
- [ ] PostgreSQL repository
- [ ] Redis-compatible worker queue

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
