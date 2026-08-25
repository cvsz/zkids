# zkids

`zkids` is a production-grade, offline-first control plane and media pipeline for original children's animation.

## v1.0 capabilities

The v1.0 baseline includes:

- typed Story / Character / Episode / Scene / Timeline contracts
- fail-closed episode and scene state machines
- image, voice, motion/video and publishing provider boundaries
- provider capability negotiation and bounded cost accounting
- immutable asset provenance and S3-compatible storage
- SQLite local development plus PostgreSQL production migrations
- Redis-compatible durable worker queue
- signed bearer authentication, RBAC and tenant isolation
- character registry/versioning
- storyboard revision control
- render-job retry/cancel operations
- QC review records
- explicit human publication approval
- publication idempotency/replay protection
- analytics ingestion and scene-level retention attribution
- multilingual episode variants and experiment/creative variants
- server-rendered `/control` operator dashboard
- API/worker/PostgreSQL/Redis/MinIO production-like Compose stack
- deterministic fake/local providers for zero-paid-call CI

Publication remains fail-closed: successful generation, rendering, QC or packaging never grants permission to publish.

## Offline quick start

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'

zkids validate examples/episode-001
zkids plan examples/episode-001/timeline.json
zkids qc examples/episode-001
zkids package examples/episode-001 --output dist/episode-001
```

The offline package remains review-only until the explicit publication state transition is approved.

## API and control plane

```bash
uvicorn zkids.api:app --host 127.0.0.1 --port 8000
```

Key surfaces:

- `GET /healthz`, `GET /readyz`
- `GET /control`
- episode/job registration and reads
- character version registry
- storyboard revisions
- render-job retry/cancel
- QC review
- analytics ingestion + retention aggregation
- multilingual/experiment variants
- explicit gate approval
- fail-closed publishing

When `ZKIDS_AUTH_SECRET` is configured, protected endpoints require signed bearer tokens and enforce tenant-scoped access. Offline development remains usable without auth configuration.

## Production dependencies

```bash
pip install -e '.[production]'
```

Provider and publisher credentials are accepted from environment variables only. They are never part of persisted job, episode, analytics or publication payloads.

## Production-like local stack

```bash
cp .env.example .env
# Replace development credentials before exposing the stack.
docker compose -f compose.production.yml up --build
```

```text
API / Control Plane
 ├─ PostgreSQL
 ├─ Redis queue
 └─ MinIO / S3-compatible object storage

Worker
 ├─ PostgreSQL
 ├─ Redis queue
 └─ Provider adapters
```

## Development and release gates

```bash
pip install -e '.[dev,production]'
ruff format --check src/zkids tests
ruff check src/zkids tests
mypy src/zkids
bandit -q -r src/zkids
pytest
docker build -t zkids:v1 .
docker compose -f compose.production.yml config
```

CI additionally retains the complete offline CLI E2E path, CodeQL and dependency review.

## Publication safety boundary

A publication request is accepted only when all of these are true:

1. the actor has `approve_publish` permission;
2. the episode is in `HUMAN_PUBLISH_APPROVED` state;
3. `human_approved` is explicit;
4. `approved_by` matches the authenticated actor;
5. the publication carries a tenant-scoped idempotency key.

CI uses only deterministic fake/local adapters. Real image, TTS, motion/Veo or publishing activation requires operator-owned provider accounts, credentials and environment configuration.
