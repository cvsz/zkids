# zkids

`zkids` is an offline-first production control plane and media-pipeline foundation for original children's animation.

## v0.2 production adapter foundation

The current baseline includes the complete v0.1 offline path plus:

- vendor-neutral image, voice, and motion/video HTTP adapter boundaries
- provider capability negotiation before expensive motion generation
- environment-only provider credentials
- local and S3-compatible object storage with immutable SHA-256 asset keys
- PostgreSQL production-job/usage-event schema foundation
- Redis-compatible worker queue and worker entrypoint
- signed bearer authentication, RBAC, and tenant-scoped episode/job access
- explicit `approve_publish` permission for human publish approval
- provider cost metering integrated with bounded budget accounting
- readiness/auth diagnostics
- production-like Compose stack with API, worker, PostgreSQL, Redis, and MinIO
- fake/local providers for CI so validation never incurs paid generation cost

The architecture keeps publication fail-closed. Packaging, rendering, or successful generation never grants permission to publish.

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

The output package remains `READY_FOR_HUMAN_REVIEW`.

## Production dependencies

```bash
pip install -e '.[production]'
```

Production extras install the PostgreSQL, Redis, and S3-compatible storage clients. Provider credentials are not accepted through request payloads; configure them using environment variables only.

## API

```bash
uvicorn zkids.api:app --host 127.0.0.1 --port 8000
```

Useful endpoints include:

- `GET /healthz`
- `GET /readyz`
- `GET /v1/auth/whoami`
- contract validation and episode/job control surfaces
- explicit state-machine approval gates
- render planning
- fail-closed publication readiness checking

When `ZKIDS_AUTH_SECRET` is set, protected endpoints require signed bearer tokens. Offline development remains usable without authentication configuration.

## Production-like local stack

```bash
cp .env.example .env
# Replace all development secrets before exposing the stack.
docker compose -f compose.production.yml up --build
```

The stack provides:

```text
API
 ├─ PostgreSQL
 ├─ Redis queue
 └─ MinIO / S3-compatible object storage

Worker
 ├─ PostgreSQL
 ├─ Redis queue
 └─ MinIO / S3-compatible object storage
```

## Development gates

```bash
pip install -e '.[dev,production]'
ruff format --check src/zkids tests/test_p1_offline.py tests/test_p2_production.py
ruff check src/zkids tests/test_p1_offline.py tests/test_p2_production.py
mypy src/zkids
bandit -q -r src/zkids
pytest
docker build -t zkids:0.2 .
docker compose -f compose.production.yml config
```

CI also retains the complete offline CLI E2E path.

## Safety boundary

Publication is a separate state transition and must never occur without explicit `HUMAN_PUBLISH_APPROVED` state. In authenticated production mode, the actor must also hold `approve_publish` permission. Provider adapters must attach provenance/cost metadata and satisfy deterministic validation before an asset becomes eligible for downstream production.
