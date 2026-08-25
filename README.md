# zkids

`zkids` is an offline-first production control plane and media-pipeline foundation for original children's animation.

## v0.1 offline vertical slice

The v0.1 baseline provides:

- explicit Episode, Scene, and Generation Job state machines
- typed prompt compilation from locked character + scene contracts
- provider capability negotiation instead of vendor-coupled orchestration
- asset lineage DAG and downstream invalidation discovery
- fail-closed deterministic QC policy with separate soft quality scores
- bounded budget accounting and idempotent generation jobs
- JSON Schema 2020-12 + typed Pydantic production contracts
- SQLite episode/job persistence with append-only audit events
- deterministic dry-run provider behavior
- timeline overlap/gap validation
- safe `ffprobe` capability/probe path
- CLI and FastAPI control-plane surfaces
- Docker and Python quality/security/offline-E2E CI

The architecture intentionally keeps real image, voice, music, motion-video, and publishing providers behind adapters. No paid provider credentials are required for the v0.1 package.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'

zkids validate examples/episode-001
zkids plan examples/episode-001/timeline.json
zkids qc examples/episode-001
zkids package examples/episode-001 --output dist/episode-001
```

The output package remains `READY_FOR_HUMAN_REVIEW`; packaging never implies permission to publish.

## API

```bash
uvicorn zkids.api:app --host 127.0.0.1 --port 8000
```

Initial endpoints include health, validation, episode registration/state, idempotent generation jobs, explicit approval gates, render planning, and a fail-closed publication readiness check.

## Development gates

```bash
ruff format --check src/zkids/api.py src/zkids/cli.py src/zkids/models.py src/zkids/runtime.py tests/test_p1_offline.py
ruff check src/zkids/api.py src/zkids/cli.py src/zkids/models.py src/zkids/runtime.py tests/test_p1_offline.py
mypy src/zkids
bandit -q -r src/zkids
pytest
```

## Container

```bash
docker build -t zkids:0.1 .
docker compose -f deploy/docker-compose.yml up --build
```

The container runs as a non-root user and the Compose baseline drops Linux capabilities, enables `no-new-privileges`, and keeps the root filesystem read-only while persisting local runtime state in the dedicated `.tmp` volume.

## Safety boundary

Publication is a separate state transition and must never occur without explicit `HUMAN_PUBLISH_APPROVED` state. Provider adapters must attach provenance and satisfy deterministic validation before an asset becomes eligible for downstream production.
