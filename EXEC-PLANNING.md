# EXEC-PLANNING

## Baseline

Architecture baseline: `docs/superpowers/specs/2026-08-26-zkids-design.md` (approved 2026-08-26).

## Slice P0 — Core execution semantics

Status: IMPLEMENTED IN THIS PR

Acceptance criteria:

1. Illegal Episode/Scene transitions fail closed.
2. Human publish approval is an explicit state before publication.
3. Motion provider requests are compiled from typed character and scene contracts.
4. Capability mismatches reject before expensive provider submission.
5. Asset lineage is acyclic and can identify descendants for invalidation.
6. Deterministic hard QC failures cannot be overridden by soft model scores.
7. Budget reservations are bounded and reject over-budget work.

## Slice P1 — Offline vertical slice

Next implementation order:

1. JSON Schema 2020-12 contracts.
2. Typed Pydantic domain models and schema loader.
3. SQLite repository + audit-event store.
4. Deterministic dry-run story/image/audio/motion/publish ports.
5. Scene planner and idempotent generation-job service.
6. Timeline normalization/compiler.
7. FFmpeg probe + optional renderer.
8. CLI `validate`, `plan`, `qc`, `package`.
9. Minimal FastAPI endpoints from the architecture spec.
10. Docker + expanded Python CI + offline E2E.

## Release gate

`v0.1.0` is not releasable until lint, formatting, strict typing, unit/contract/security tests, Docker build, CLI smoke, and offline E2E pass. No real paid provider integration is required for v0.1.0.

## Rollback

P0 is additive. Rollback is the single feature commit/PR; no persistent production schema or external provider mutation is introduced.
