from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS series (
    series_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS characters (
    character_id TEXT PRIMARY KEY,
    series_id TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    data TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS episodes (
    episode_id TEXT PRIMARY KEY,
    series_id TEXT,
    title TEXT,
    state TEXT NOT NULL DEFAULT 'draft',
    data TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS scenes (
    scene_id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    index_num INTEGER NOT NULL,
    duration REAL NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assets (
    asset_id TEXT PRIMARY KEY,
    episode_id TEXT,
    scene_id TEXT,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    approved INTEGER NOT NULL DEFAULT 0,
    data TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS voices (
    voice_id TEXT PRIMARY KEY,
    character_id TEXT,
    provider_voice_name TEXT,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS generation_jobs (
    job_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    episode_id TEXT,
    scene_id TEXT,
    state TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    quality_tier TEXT NOT NULL DEFAULT 'draft',
    provider TEXT,
    model TEXT,
    payload_hash TEXT,
    error TEXT,
    cost_estimate_usd REAL NOT NULL DEFAULT 0,
    artifacts TEXT NOT NULL DEFAULT '[]',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS renders (
    render_id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    path TEXT,
    qc_state TEXT NOT NULL DEFAULT 'pending',
    duration REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS qc_results (
    qc_id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id TEXT,
    scene_id TEXT,
    target_path TEXT,
    category TEXT NOT NULL,
    passed INTEGER NOT NULL,
    details TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS gates (
    gate_id INTEGER NOT NULL,
    episode_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    note TEXT,
    approver TEXT,
    decided_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (gate_id, episode_id)
);
CREATE TABLE IF NOT EXISTS publications (
    publication_id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    package_path TEXT,
    status TEXT NOT NULL DEFAULT 'prepared',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.conn.execute(sql, params)
        self.conn.commit()

    def query_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def query_all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def upsert(self, table: str, pk: str, row: dict[str, Any]) -> None:
        cols = list(row.keys())
        placeholders = ", ".join("?" for _ in cols)
        updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != pk)
        sql = (
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT({pk}) DO UPDATE SET {updates}"
        )
        self.execute(sql, tuple(row.values()))

    @staticmethod
    def dump(model: Any) -> str:
        if hasattr(model, "model_dump_json"):
            return model.model_dump_json()
        return json.dumps(model)

    @staticmethod
    def sha(payload: Any) -> str:
        if not isinstance(payload, str):
            payload = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "untitled"
