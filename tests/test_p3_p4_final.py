from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from zkids.api import app, store
from zkids.control_plane import ControlPlaneError, ControlPlaneService
from zkids.states import EpisodeState


def test_character_storyboard_qc_and_dashboard_are_tenant_scoped() -> None:
    service = ControlPlaneService(sqlite3.connect(":memory:"))
    service.put_character(
        "tenant-a",
        {
            "character_id": "MIMI",
            "version": "v1",
            "name": "Mimi",
            "immutable_traits": {"fur": "white"},
        },
    )
    service.put_character(
        "tenant-b",
        {
            "character_id": "BORI",
            "version": "v1",
            "name": "Bori",
            "immutable_traits": {"fur": "brown"},
        },
    )
    assert [item["character_id"] for item in service.list_characters("tenant-a")] == ["MIMI"]
    service.put_storyboard("tenant-a", "EP1", {"revision": 1, "scenes": [{"id": "S1"}]})
    assert service.latest_storyboard("tenant-a", "EP1") == {
        "revision": 1,
        "scenes": [{"id": "S1"}],
    }
    review = service.review_qc("tenant-a", "S1", "alice", "PASS", "looks good")
    assert review["decision"] == "PASS"
    with pytest.raises(ControlPlaneError):
        service.review_qc("tenant-a", "S1", "alice", "UNKNOWN", "")
    assert service.dashboard("tenant-a")["characters"] == 1
    assert service.dashboard("tenant-b")["characters"] == 1


def test_analytics_retention_and_event_idempotency() -> None:
    service = ControlPlaneService(sqlite3.connect(":memory:"))
    event = {
        "event_id": "E1",
        "episode_id": "EP1",
        "scene_id": "S1",
        "event_type": "retention",
        "value": 0.75,
        "position_seconds": 8,
    }
    service.ingest_analytics("tenant-a", event)
    service.ingest_analytics("tenant-a", event)
    service.ingest_analytics(
        "tenant-a",
        {**event, "event_id": "E2", "value": 0.25},
    )
    rows = service.scene_retention("tenant-a", "EP1")
    assert rows == [{"scene_id": "S1", "average_retention": 0.5, "samples": 2}]


def test_variants_and_publication_are_idempotent_and_fail_closed() -> None:
    service = ControlPlaneService(sqlite3.connect(":memory:"))
    variant = service.put_variant(
        "tenant-a",
        "EP1",
        {"variant_id": "th-v1", "language": "th", "experiment_id": "EXP1"},
    )
    assert variant["language"] == "th"
    with pytest.raises(ControlPlaneError):
        service.publish_fake(
            "tenant-a",
            "EP1",
            idempotency_key="EP1:youtube:v1",
            destination="youtube-dry-run",
            approved=False,
            approved_by=None,
            metadata={},
        )
    first = service.publish_fake(
        "tenant-a",
        "EP1",
        idempotency_key="EP1:youtube:v1",
        destination="youtube-dry-run",
        approved=True,
        approved_by="alice",
        metadata={"title": "Episode 1"},
    )
    second = service.publish_fake(
        "tenant-a",
        "EP1",
        idempotency_key="EP1:youtube:v1",
        destination="youtube-dry-run",
        approved=True,
        approved_by="alice",
        metadata={"title": "Episode 1 duplicate"},
    )
    assert first.reused is False
    assert second.reused is True
    assert second.external_id == first.external_id


def test_final_control_plane_ui_and_publish_gate() -> None:
    client = TestClient(app)
    dashboard = client.get("/control")
    assert dashboard.status_code == 200
    assert "zkids Control Plane" in dashboard.text

    episode_id = "EP-FINAL-TEST"
    store.put_episode(
        episode_id,
        {
            "episode_id": episode_id,
            "series_id": "SERIES1",
            "title": "Final test",
            "language": "th",
            "duration_target": 8,
            "scenes": [],
            "max_retries_per_scene": 3,
            "budget_limit": 0,
            "tenant_id": "local",
        },
        EpisodeState.FINAL_QC_APPROVED,
    )
    blocked = client.post(
        f"/v1/episodes/{episode_id}/publish",
        json={
            "idempotency_key": f"{episode_id}:youtube:v1",
            "destination": "youtube-dry-run",
            "human_approved": True,
            "approved_by": "offline",
        },
    )
    assert blocked.status_code == 409

    approved = client.post(
        f"/v1/episodes/{episode_id}/gates/{EpisodeState.HUMAN_PUBLISH_APPROVED.value}",
        json={"approved": True},
    )
    assert approved.status_code == 200
    published = client.post(
        f"/v1/episodes/{episode_id}/publish",
        json={
            "idempotency_key": f"{episode_id}:youtube:v1",
            "destination": "youtube-dry-run",
            "human_approved": True,
            "approved_by": "offline",
            "metadata": {"title": "Final test"},
        },
    )
    assert published.status_code == 200
    assert published.json()["external_id"].startswith("dry-publish-")
