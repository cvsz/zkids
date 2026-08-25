from __future__ import annotations

import json
import sqlite3
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .states import EpisodeState, GenerationJobState, SceneState, transition


class RuntimeErrorZKids(RuntimeError):
    pass


def safe_child(root: Path, relative: str) -> Path:
    root = root.resolve()
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise RuntimeErrorZKids(f"path escapes root: {relative}")
    return candidate


class SQLiteStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS episodes (
              episode_id TEXT PRIMARY KEY,
              payload TEXT NOT NULL,
              state TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS jobs (
              job_id TEXT PRIMARY KEY,
              idempotency_key TEXT NOT NULL UNIQUE,
              payload TEXT NOT NULL,
              state TEXT NOT NULL,
              attempts INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS audit_events (
              seq INTEGER PRIMARY KEY AUTOINCREMENT,
              event_type TEXT NOT NULL,
              entity_id TEXT NOT NULL,
              payload TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self.conn.commit()

    def audit(self, event_type: str, entity_id: str, payload: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT INTO audit_events(event_type, entity_id, payload) VALUES (?, ?, ?)",
            (event_type, entity_id, json.dumps(payload, sort_keys=True)),
        )
        self.conn.commit()

    def put_episode(self, episode_id: str, payload: dict[str, Any], state: EpisodeState) -> None:
        self.conn.execute(
            "INSERT INTO episodes VALUES (?, ?, ?) ON CONFLICT(episode_id) DO UPDATE SET payload=excluded.payload,state=excluded.state",
            (episode_id, json.dumps(payload, sort_keys=True), state.value),
        )
        self.conn.commit()
        self.audit("episode.upserted", episode_id, {"state": state.value})

    def get_episode(self, episode_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT payload, state FROM episodes WHERE episode_id=?", (episode_id,)
        ).fetchone()
        if not row:
            return None
        payload = json.loads(row[0])
        payload["state"] = row[1]
        return payload

    def create_job(self, job_id: str, idempotency_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT job_id, payload, state, attempts FROM jobs WHERE idempotency_key=?",
            (idempotency_key,),
        ).fetchone()
        if row:
            return {"job_id": row[0], "payload": json.loads(row[1]), "state": row[2], "attempts": row[3], "reused": True}
        self.conn.execute(
            "INSERT INTO jobs(job_id,idempotency_key,payload,state) VALUES (?,?,?,?)",
            (job_id, idempotency_key, json.dumps(payload, sort_keys=True), GenerationJobState.PENDING.value),
        )
        self.conn.commit()
        self.audit("job.created", job_id, {"idempotency_key": idempotency_key})
        return {"job_id": job_id, "payload": payload, "state": GenerationJobState.PENDING.value, "attempts": 0, "reused": False}


@dataclass(frozen=True)
class TimelineItem:
    scene_id: str
    start: float
    duration: float
    video: str | None = None
    voice: str | None = None


def compile_timeline(items: list[TimelineItem]) -> dict[str, Any]:
    ordered = sorted(items, key=lambda i: i.start)
    previous_end = 0.0
    warnings: list[str] = []
    for item in ordered:
        if item.duration <= 0:
            raise RuntimeErrorZKids(f"non-positive duration: {item.scene_id}")
        if item.start < previous_end:
            raise RuntimeErrorZKids(f"timeline overlap at {item.scene_id}")
        if item.start > previous_end:
            warnings.append(f"gap:{previous_end:.3f}-{item.start:.3f}")
        previous_end = item.start + item.duration
    return {"duration": previous_end, "items": [asdict(item) for item in ordered], "warnings": warnings}


def ffprobe(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeErrorZKids(f"media does not exist: {path}")
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeErrorZKids(proc.stderr.strip() or "ffprobe failed")
    return json.loads(proc.stdout)


class DryRunProvider:
    name = "dry-run"

    def generate(self, kind: str, request: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider": self.name,
            "kind": kind,
            "status": "generated",
            "asset_uri": f"dry-run://{kind}/{request.get('scene_id', request.get('episode_id', 'asset'))}",
            "provenance": {"provider": self.name, "model": "deterministic-v1", "request": request},
        }


def validate_scene_progression(current: SceneState, target: SceneState) -> SceneState:
    return transition(current, target)
