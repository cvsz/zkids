from __future__ import annotations

from pathlib import Path

import pytest

from zkids.auth import AuthError, Role, issue_token, verify_token
from zkids.domain import BudgetError
from zkids.infrastructure import LocalObjectStore, immutable_asset_key, retry_delay_seconds
from zkids.production import ProductionExecutor
from zkids.providers import FakeProvider, MotionProvider, HTTPProviderConfig


def test_auth_rbac_and_tenant_claims() -> None:
    token = issue_token(
        subject="alice", tenant_id="tenant-a", role=Role.PUBLISHER, ttl_seconds=60, secret="test-secret"
    )
    principal = verify_token(token, secret="test-secret", now=1)
    assert principal.tenant_id == "tenant-a"
    principal.require("approve_publish")
    with pytest.raises(AuthError):
        issue_token(subject="x", tenant_id="t", role=Role.VIEWER, secret="")


def test_local_object_store_is_content_addressable_and_scoped(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path)
    data = b"hello"
    key = immutable_asset_key(tenant_id="t1", episode_id="e1", data=data, suffix="bin")
    uri = store.put_bytes(key, data, content_type="application/octet-stream")
    assert uri.startswith("file://")
    assert store.get_bytes(key) == data


def test_production_executor_records_cost_and_enforces_budget() -> None:
    executor = ProductionExecutor()
    provider = FakeProvider("image", cost_usd=0.25)
    result = executor.generate(
        tenant_id="tenant-a",
        operation="image",
        provider=provider,
        request={"scene_id": "s1", "estimated_cost_usd": 0.25},
        budget_limit=1.0,
    )
    assert result.asset_uri == "fake://image/s1"
    assert executor.usage.events[0].cost_usd == 0.25
    with pytest.raises(BudgetError):
        executor.generate(
            tenant_id="tenant-a",
            operation="image",
            provider=FakeProvider("image", cost_usd=2.0),
            request={"scene_id": "s2", "estimated_cost_usd": 2.0},
            budget_limit=1.0,
        )


def test_motion_adapter_builds_veo_capable_shape() -> None:
    adapter = MotionProvider(
        HTTPProviderConfig(
            name="veo-compatible",
            endpoint="https://example.invalid/videos",
            model="veo-model",
            api_key_env="NEVER_SET",
        )
    )
    payload = adapter.build_payload(
        {
            "prompt": "walk",
            "image_uri": "s3://bucket/still.png",
            "duration": 8,
            "aspect_ratio": "16:9",
            "resolution": "1080p",
            "reference_uris": ["s3://bucket/ref.png"],
        }
    )
    assert payload["duration"] == 8
    assert payload["reference_uris"]


def test_retry_backoff_is_bounded() -> None:
    assert retry_delay_seconds(1) == 1.0
    assert retry_delay_seconds(10, cap=30.0) == 30.0
