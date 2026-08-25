from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


class PublishingError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PublishingReceipt:
    provider: str
    external_id: str
    destination: str
    metadata: dict[str, Any]


class PublishingProvider(Protocol):
    name: str

    def publish(self, request: dict[str, Any]) -> PublishingReceipt: ...


class FakePublishingProvider:
    name = "fake-publisher"

    def publish(self, request: dict[str, Any]) -> PublishingReceipt:
        episode_id = str(request.get("episode_id", "episode"))
        destination = str(request.get("destination", "youtube-dry-run"))
        return PublishingReceipt(
            provider=self.name,
            external_id=f"fake://{destination}/{episode_id}",
            destination=destination,
            metadata=dict(request.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class HTTPPublishingConfig:
    name: str
    endpoint: str
    api_key_env: str
    timeout_seconds: float = 30.0


class HTTPPublishingProvider:
    """Vendor-neutral publishing boundary.

    Credentials are read only from the configured environment variable. CI does not instantiate
    or call this adapter; it exists for explicit operator-configured production activation.
    """

    def __init__(self, config: HTTPPublishingConfig) -> None:
        self.config = config
        self.name = config.name

    def publish(self, request: dict[str, Any]) -> PublishingReceipt:
        key = os.getenv(self.config.api_key_env)
        if not key:
            raise PublishingError(f"missing publishing credential: {self.config.api_key_env}")
        body = json.dumps(request, sort_keys=True).encode("utf-8")
        http_request = urllib.request.Request(  # nosec B310 - operator-configured HTTPS endpoint
            self.config.endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(  # nosec B310 - operator-configured HTTPS endpoint
                http_request,
                timeout=self.config.timeout_seconds,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise PublishingError("publishing provider request failed") from exc
        external_id = str(payload.get("external_id", payload.get("id", ""))).strip()
        if not external_id:
            raise PublishingError("publishing provider response missing external id")
        return PublishingReceipt(
            provider=self.name,
            external_id=external_id,
            destination=str(request.get("destination", self.name)),
            metadata=dict(payload),
        )
