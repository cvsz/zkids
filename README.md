# zkids

`zkids` is an offline-first production control plane and media-pipeline foundation for original children's animation.

## v0.1 foundation

The first implementation slice establishes:

- explicit Episode, Scene, and Generation Job state machines
- typed prompt compilation from locked character + scene contracts
- provider capability negotiation instead of vendor-coupled orchestration
- asset lineage DAG and downstream invalidation discovery
- fail-closed deterministic QC policy with separate soft quality scores
- bounded budget accounting for generation work

The architecture intentionally keeps real image, voice, music, motion-video, and publishing providers behind adapters. No paid provider credentials are required for the core package.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
ruff check .
mypy src/zkids
pytest
```

## Safety boundary

Publication is a separate state transition and must never occur without explicit `HUMAN_PUBLISH_APPROVED` state. Provider adapters must attach provenance and satisfy deterministic validation before an asset becomes eligible for downstream production.
