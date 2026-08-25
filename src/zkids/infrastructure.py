from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class InfrastructureError(RuntimeError):
    pass


class ObjectStore(Protocol):
    def put_bytes(self, key: str, data: bytes, *, content_type: str) -> str: ...

    def get_bytes(self, key: str) -> bytes: ...


class LocalObjectStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise InfrastructureError("object key escapes storage root")
        return candidate

    def put_bytes(self, key: str, data: bytes, *, content_type: str) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        metadata = {"content_type": content_type, "sha256": hashlib.sha256(data).hexdigest()}
        path.with_suffix(path.suffix + ".meta.json").write_text(
            json.dumps(metadata, sort_keys=True), encoding="utf-8"
        )
        return f"file://{path}"

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()


class S3ObjectStore:
    def __init__(self, *, bucket: str, endpoint_url: str | None = None) -> None:
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - optional production dependency
            raise InfrastructureError("install zkids[production] for S3 support") from exc
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )

    def put_bytes(self, key: str, data: bytes, *, content_type: str) -> str:
        digest = hashlib.sha256(data).hexdigest()
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata={"sha256": digest},
        )
        return f"s3://{self.bucket}/{key}"

    def get_bytes(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return bytes(response["Body"].read())


@dataclass(frozen=True, slots=True)
class QueueMessage:
    job_id: str
    payload: dict[str, Any]


class RedisQueue:
    def __init__(self, url: str, queue_name: str = "zkids:jobs") -> None:
        try:
            import redis
        except ImportError as exc:  # pragma: no cover
            raise InfrastructureError("install zkids[production] for Redis support") from exc
        self.client = redis.Redis.from_url(url, decode_responses=True)
        self.queue_name = queue_name

    def enqueue(self, message: QueueMessage) -> None:
        self.client.rpush(
            self.queue_name, json.dumps({"job_id": message.job_id, "payload": message.payload})
        )

    def lease(self, timeout_seconds: int = 5) -> QueueMessage | None:
        item = self.client.blpop(self.queue_name, timeout=timeout_seconds)
        if item is None:
            return None
        _, raw = item
        payload = json.loads(raw)
        return QueueMessage(job_id=payload["job_id"], payload=payload["payload"])


class PostgresRepository:
    def __init__(self, dsn: str) -> None:
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover
            raise InfrastructureError("install zkids[production] for PostgreSQL support") from exc
        self.psycopg = psycopg
        self.dsn = dsn

    def migrate(self) -> None:
        with self.psycopg.connect(self.dsn) as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS production_jobs (
                  job_id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL,
                  payload JSONB NOT NULL,
                  state TEXT NOT NULL,
                  attempts INTEGER NOT NULL DEFAULT 0,
                  leased_until DOUBLE PRECISION,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                  UNIQUE (tenant_id, idempotency_key)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_events (
                  seq BIGSERIAL PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  provider TEXT NOT NULL,
                  model TEXT NOT NULL,
                  operation TEXT NOT NULL,
                  cost_usd DOUBLE PRECISION NOT NULL,
                  metadata JSONB NOT NULL,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

    def record_usage(
        self,
        *,
        tenant_id: str,
        provider: str,
        model: str,
        operation: str,
        cost_usd: float,
        metadata: dict[str, Any],
    ) -> None:
        with self.psycopg.connect(self.dsn) as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO usage_events(tenant_id,provider,model,operation,cost_usd,metadata) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (tenant_id, provider, model, operation, cost_usd, json.dumps(metadata)),
            )


def immutable_asset_key(*, tenant_id: str, episode_id: str, data: bytes, suffix: str) -> str:
    digest = hashlib.sha256(data).hexdigest()
    safe_suffix = suffix.lstrip(".")
    return f"tenants/{tenant_id}/episodes/{episode_id}/sha256/{digest}.{safe_suffix}"


def retry_delay_seconds(attempt: int, *, base: float = 1.0, cap: float = 30.0) -> float:
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    return min(cap, base * (2 ** (attempt - 1)))


def lease_deadline(seconds: int) -> float:
    return time.time() + seconds
