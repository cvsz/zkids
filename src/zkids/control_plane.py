from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from typing import Any


class ControlPlaneError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PublishResult:
    publication_id: str
    destination: str
    external_id: str
    reused: bool


class ControlPlaneService:
    """Durable P3/P4 control-plane records backed by the existing SQLite connection.

    Production PostgreSQL deployments can mirror these tables using the migration SQL shipped
    with this release. The service intentionally stores metadata only; provider credentials and
    media bytes stay outside the database.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS character_versions (
              tenant_id TEXT NOT NULL,
              character_id TEXT NOT NULL,
              version TEXT NOT NULL,
              payload TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (tenant_id, character_id, version)
            );
            CREATE TABLE IF NOT EXISTS storyboards (
              tenant_id TEXT NOT NULL,
              episode_id TEXT NOT NULL,
              revision INTEGER NOT NULL,
              payload TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (tenant_id, episode_id, revision)
            );
            CREATE TABLE IF NOT EXISTS qc_reviews (
              tenant_id TEXT NOT NULL,
              entity_id TEXT NOT NULL,
              reviewer TEXT NOT NULL,
              decision TEXT NOT NULL,
              notes TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS analytics_events (
              tenant_id TEXT NOT NULL,
              event_id TEXT NOT NULL,
              episode_id TEXT NOT NULL,
              scene_id TEXT,
              event_type TEXT NOT NULL,
              position_seconds REAL,
              value REAL,
              payload TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (tenant_id, event_id)
            );
            CREATE TABLE IF NOT EXISTS episode_variants (
              tenant_id TEXT NOT NULL,
              episode_id TEXT NOT NULL,
              variant_id TEXT NOT NULL,
              language TEXT NOT NULL,
              experiment_id TEXT,
              payload TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (tenant_id, episode_id, variant_id)
            );
            CREATE TABLE IF NOT EXISTS publications (
              tenant_id TEXT NOT NULL,
              publication_id TEXT NOT NULL,
              episode_id TEXT NOT NULL,
              idempotency_key TEXT NOT NULL,
              destination TEXT NOT NULL,
              external_id TEXT NOT NULL,
              payload TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (tenant_id, publication_id),
              UNIQUE (tenant_id, idempotency_key)
            );
            """
        )
        self.conn.commit()

    def put_character(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        character_id = _required(payload, "character_id")
        version = _required(payload, "version")
        self.conn.execute(
            "INSERT INTO character_versions(tenant_id,character_id,version,payload) VALUES (?,?,?,?) "
            "ON CONFLICT(tenant_id,character_id,version) DO UPDATE SET payload=excluded.payload",
            (tenant_id, character_id, version, _json(payload)),
        )
        self.conn.commit()
        return {"character_id": character_id, "version": version, "tenant_id": tenant_id}

    def list_characters(self, tenant_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT payload FROM character_versions WHERE tenant_id=? ORDER BY character_id,version",
            (tenant_id,),
        ).fetchall()
        return [dict(json.loads(row[0])) for row in rows]

    def put_storyboard(
        self, tenant_id: str, episode_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        revision = int(payload.get("revision", 1))
        if revision < 1:
            raise ControlPlaneError("revision must be >= 1")
        self.conn.execute(
            "INSERT INTO storyboards(tenant_id,episode_id,revision,payload) VALUES (?,?,?,?) "
            "ON CONFLICT(tenant_id,episode_id,revision) DO UPDATE SET payload=excluded.payload",
            (tenant_id, episode_id, revision, _json(payload)),
        )
        self.conn.commit()
        return {"episode_id": episode_id, "revision": revision}

    def latest_storyboard(self, tenant_id: str, episode_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT payload FROM storyboards WHERE tenant_id=? AND episode_id=? "
            "ORDER BY revision DESC LIMIT 1",
            (tenant_id, episode_id),
        ).fetchone()
        return None if row is None else dict(json.loads(row[0]))

    def review_qc(
        self,
        tenant_id: str,
        entity_id: str,
        reviewer: str,
        decision: str,
        notes: str,
    ) -> dict[str, str]:
        if decision not in {"PASS", "RETRY", "MANUAL_REVIEW", "FAIL"}:
            raise ControlPlaneError("invalid QC decision")
        self.conn.execute(
            "INSERT INTO qc_reviews(tenant_id,entity_id,reviewer,decision,notes) VALUES (?,?,?,?,?)",
            (tenant_id, entity_id, reviewer, decision, notes),
        )
        self.conn.commit()
        return {"entity_id": entity_id, "decision": decision, "reviewer": reviewer}

    def ingest_analytics(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        event_id = _required(payload, "event_id")
        episode_id = _required(payload, "episode_id")
        event_type = _required(payload, "event_type")
        self.conn.execute(
            "INSERT OR IGNORE INTO analytics_events(tenant_id,event_id,episode_id,scene_id,event_type,"
            "position_seconds,value,payload) VALUES (?,?,?,?,?,?,?,?)",
            (
                tenant_id,
                event_id,
                episode_id,
                payload.get("scene_id"),
                event_type,
                payload.get("position_seconds"),
                payload.get("value"),
                _json(payload),
            ),
        )
        self.conn.commit()
        return {"event_id": event_id, "accepted": True}

    def scene_retention(self, tenant_id: str, episode_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT scene_id,AVG(value),COUNT(*) FROM analytics_events "
            "WHERE tenant_id=? AND episode_id=? AND event_type='retention' AND scene_id IS NOT NULL "
            "GROUP BY scene_id ORDER BY scene_id",
            (tenant_id, episode_id),
        ).fetchall()
        return [
            {"scene_id": row[0], "average_retention": float(row[1]), "samples": int(row[2])}
            for row in rows
        ]

    def put_variant(
        self, tenant_id: str, episode_id: str, payload: dict[str, Any]
    ) -> dict[str, str]:
        variant_id = _required(payload, "variant_id")
        language = _required(payload, "language")
        self.conn.execute(
            "INSERT INTO episode_variants(tenant_id,episode_id,variant_id,language,experiment_id,payload) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(tenant_id,episode_id,variant_id) DO UPDATE SET "
            "language=excluded.language,experiment_id=excluded.experiment_id,payload=excluded.payload",
            (
                tenant_id,
                episode_id,
                variant_id,
                language,
                payload.get("experiment_id"),
                _json(payload),
            ),
        )
        self.conn.commit()
        return {"episode_id": episode_id, "variant_id": variant_id, "language": language}

    def publish_fake(
        self,
        tenant_id: str,
        episode_id: str,
        *,
        idempotency_key: str,
        destination: str,
        approved: bool,
        approved_by: str | None,
        metadata: dict[str, Any],
    ) -> PublishResult:
        if not approved or not approved_by:
            raise ControlPlaneError("human publish approval is required")
        idempotency_key = idempotency_key.strip()
        if not idempotency_key:
            raise ControlPlaneError("idempotency_key is required")
        destination = destination.strip()
        if not destination:
            raise ControlPlaneError("destination is required")
        prior = self.conn.execute(
            "SELECT publication_id,destination,external_id FROM publications "
            "WHERE tenant_id=? AND idempotency_key=?",
            (tenant_id, idempotency_key),
        ).fetchone()
        if prior:
            return PublishResult(str(prior[0]), str(prior[1]), str(prior[2]), True)
        publication_id = hashlib.sha256(
            f"{tenant_id}:{episode_id}:{idempotency_key}".encode()
        ).hexdigest()[:20]
        external_id = f"dry-publish-{publication_id}"
        payload = {
            "episode_id": episode_id,
            "approved_by": approved_by,
            "metadata": metadata,
        }
        self.conn.execute(
            "INSERT INTO publications(tenant_id,publication_id,episode_id,idempotency_key,destination,"
            "external_id,payload) VALUES (?,?,?,?,?,?,?)",
            (
                tenant_id,
                publication_id,
                episode_id,
                idempotency_key,
                destination,
                external_id,
                _json(payload),
            ),
        )
        self.conn.commit()
        return PublishResult(publication_id, destination, external_id, False)

    def dashboard(self, tenant_id: str) -> dict[str, int]:
        tables = {
            "characters": "character_versions",
            "storyboards": "storyboards",
            "qc_reviews": "qc_reviews",
            "analytics_events": "analytics_events",
            "variants": "episode_variants",
            "publications": "publications",
        }
        result: dict[str, int] = {}
        for key, table in tables.items():
            row = self.conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE tenant_id=?",  # nosec B608 - fixed table map
                (tenant_id,),
            ).fetchone()
            result[key] = int(row[0]) if row else 0
        return result


def _required(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key, "")).strip()
    if not value:
        raise ControlPlaneError(f"{key} is required")
    return value


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
