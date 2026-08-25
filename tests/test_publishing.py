from __future__ import annotations

import pytest

from zkids.publishing import (
    FakePublishingProvider,
    HTTPPublishingConfig,
    HTTPPublishingProvider,
    PublishingError,
)


def test_fake_publisher_is_deterministic_and_offline() -> None:
    publisher = FakePublishingProvider()
    request = {
        "episode_id": "EP1",
        "destination": "youtube-dry-run",
        "metadata": {"title": "Episode 1"},
    }
    first = publisher.publish(request)
    second = publisher.publish(request)
    assert first == second
    assert first.external_id == "fake://youtube-dry-run/EP1"


def test_http_publisher_fails_closed_without_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZKIDS_TEST_PUBLISH_KEY", raising=False)
    publisher = HTTPPublishingProvider(
        HTTPPublishingConfig(
            name="youtube-compatible",
            endpoint="https://example.invalid/publish",
            api_key_env="ZKIDS_TEST_PUBLISH_KEY",
        )
    )
    with pytest.raises(PublishingError, match="missing publishing credential"):
        publisher.publish({"episode_id": "EP1"})
