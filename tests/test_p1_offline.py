from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from zkids.api import app
from zkids.models import Publication
from zkids.runtime import DryRunProvider, RuntimeErrorZKids, SQLiteStore, TimelineItem, compile_timeline, safe_child


def test_timeline_compiles_without_gaps() -> None:
    plan = compile_timeline([
        TimelineItem("S1", 0, 8),
        TimelineItem("S2", 8, 8),
    ])
    assert plan["duration"] == 16
    assert plan["warnings"] == []


def test_timeline_rejects_overlap() -> None:
    with pytest.raises(RuntimeErrorZKids):
        compile_timeline([TimelineItem("S1", 0, 8), TimelineItem("S2", 7, 8)])


def test_safe_child_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(RuntimeErrorZKids):
        safe_child(tmp_path, "../escape")


def test_job_idempotency(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "zkids.db")
    first = store.create_job("J1", "EP1:S1:motion:v1", {"scene_id": "S1"})
    second = store.create_job("J2", "EP1:S1:motion:v1", {"scene_id": "S1"})
    assert first["reused"] is False
    assert second["reused"] is True
    assert second["job_id"] == "J1"


def test_dry_run_provider_is_deterministic() -> None:
    provider = DryRunProvider()
    a = provider.generate("motion", {"scene_id": "S1"})
    b = provider.generate("motion", {"scene_id": "S1"})
    assert a == b
    assert a["asset_uri"] == "dry-run://motion/S1"


def test_publication_fails_closed() -> None:
    with pytest.raises(ValueError):
        Publication(episode_id="EP1").assert_publishable()


def test_health_and_validation() -> None:
    client = TestClient(app)
    assert client.get("/healthz").json() == {"status": "ok"}
    payload = {
        "kind": "episode",
        "data": {
            "episode_id": "EP1",
            "series_id": "SERIES1",
            "title": "Test",
            "language": "th",
            "duration_target": 8,
            "scenes": [{
                "scene_id": "S1",
                "start": 0,
                "duration": 8,
                "characters": ["C1"],
                "action": "walk",
                "camera": {},
            }],
        },
    }
    response = client.post("/v1/validate", json=payload)
    assert response.status_code == 200
    assert response.json()["valid"] is True
