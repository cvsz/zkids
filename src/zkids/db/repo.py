from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from ..models import AssetKind, AssetProvenance, EpisodeScript, GenerationJob, JobState, SceneManifest, Storyboard
from .database import Database


class FactoryRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save_series(self, series) -> None:
        self.db.upsert(
            "series",
            "series_id",
            {"series_id": series.series_id, "name": series.name, "data": self.db.dump(series)},
        )

    def get_series(self, series_id: str):
        row = self.db.query_one("SELECT data FROM series WHERE series_id=?", (series_id,))
        if not row:
            return None
        from ..models import SeriesBible

        return SeriesBible.model_validate_json(row["data"])

    def save_character(self, character, series_id: str | None = None) -> None:
        self.db.upsert(
            "characters",
            "character_id",
            {
                "character_id": character.character_id,
                "series_id": series_id,
                "version": character.version,
                "data": self.db.dump(character),
            },
        )

    def get_characters_for_series(self, series_id: str | None = None) -> list:
        from ..models import CharacterSpec

        rows = self.db.query_all(
            "SELECT data FROM characters WHERE (? IS NULL OR series_id=?)", (series_id, series_id)
        )
        return [CharacterSpec.model_validate(json.loads(r["data"])) for r in rows]

    def save_episode_script(self, script: EpisodeScript) -> None:
        self.db.upsert(
            "episodes",
            "episode_id",
            {
                "episode_id": script.episode_id,
                "series_id": script.series_id,
                "title": script.title,
                "state": "scripted",
                "data": self.db.dump(script),
            },
        )
        for i, scene in enumerate(script.scenes):
            self.db.upsert(
                "scenes",
                "scene_id",
                {
                    "scene_id": f"{script.episode_id}-{scene.scene_id}",
                    "episode_id": script.episode_id,
                    "index_num": i,
                    "duration": scene.duration_target,
                    "data": self.db.dump(scene),
                },
            )

    def get_episode_script(self, episode_id: str) -> EpisodeScript | None:
        row = self.db.query_one("SELECT data FROM episodes WHERE episode_id=?", (episode_id,))
        if not row:
            return None
        return EpisodeScript.model_validate_json(row["data"])

    def set_episode_state(self, episode_id: str, state: str) -> None:
        self.db.execute(
            "UPDATE episodes SET state=?, updated_at=CURRENT_TIMESTAMP WHERE episode_id=?",
            (state, episode_id),
        )

    def save_storyboard(self, sb: Storyboard) -> None:
        path_key = f"storyboard:{sb.episode_id}"
        self.db.upsert(
            "assets",
            "asset_id",
            {
                "asset_id": path_key,
                "episode_id": sb.episode_id,
                "scene_id": None,
                "kind": AssetKind.STORYBOARD.value,
                "path": "",
                "approved": 0,
                "data": self.db.dump(sb),
            },
        )

    def get_storyboard(self, episode_id: str) -> Storyboard | None:
        row = self.db.query_one(
            "SELECT data FROM assets WHERE asset_id=?", (f"storyboard:{episode_id}",)
        )
        if not row:
            return None
        return Storyboard.model_validate_json(row["data"])

    def save_manifest(self, manifest: SceneManifest) -> None:
        self.db.upsert(
            "assets",
            "asset_id",
            {
                "asset_id": f"manifest:{manifest.episode_id}",
                "episode_id": manifest.episode_id,
                "scene_id": None,
                "kind": AssetKind.MANIFEST.value,
                "path": "",
                "approved": 0,
                "data": self.db.dump(manifest),
            },
        )

    def get_manifest(self, episode_id: str) -> SceneManifest | None:
        row = self.db.query_one(
            "SELECT data FROM assets WHERE asset_id=?", (f"manifest:{episode_id}",)
        )
        if not row:
            return None
        return SceneManifest.model_validate_json(row["data"])

    def save_job(self, job: GenerationJob) -> None:
        self.db.upsert(
            "generation_jobs",
            "job_id",
            {
                "job_id": job.job_id,
                "kind": job.kind.value,
                "episode_id": job.episode_id,
                "scene_id": job.scene_id,
                "state": job.state.value,
                "attempts": job.attempts,
                "max_retries": job.max_retries,
                "quality_tier": job.quality_tier.value,
                "provider": job.provider,
                "model": job.model,
                "payload_hash": job.payload_hash,
                "error": job.error,
                "cost_estimate_usd": job.cost_estimate_usd,
                "artifacts": json.dumps(job.artifacts),
            },
        )

    def get_job(self, job_id: str) -> GenerationJob | None:
        row = self.db.query_one("SELECT * FROM generation_jobs WHERE job_id=?", (job_id,))
        return self._row_to_job(row) if row else None

    def jobs_for_episode(self, episode_id: str, kind: str | None = None) -> list[GenerationJob]:
        if kind:
            rows = self.db.query_all(
                "SELECT * FROM generation_jobs WHERE episode_id=? AND kind=? ORDER BY job_id",
                (episode_id, kind),
            )
        else:
            rows = self.db.query_all(
                "SELECT * FROM generation_jobs WHERE episode_id=? ORDER BY job_id", (episode_id,)
            )
        return [j for j in (self._row_to_job(r) for r in rows) if j]

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> GenerationJob:
        return GenerationJob(
            job_id=row["job_id"],
            kind=row["kind"],
            scene_id=row["scene_id"],
            episode_id=row["episode_id"],
            state=row["state"],
            attempts=row["attempts"],
            max_retries=row["max_retries"],
            quality_tier=row["quality_tier"],
            provider=row["provider"] or "unknown",
            model=row["model"],
            payload_hash=row["payload_hash"],
            error=row["error"],
            cost_estimate_usd=row["cost_estimate_usd"],
            artifacts=json.loads(row["artifacts"]),
        )

    def record_asset(self, prov: AssetProvenance) -> None:
        self.db.upsert(
            "assets",
            "asset_id",
            {
                "asset_id": prov.asset_id,
                "episode_id": prov.episode_id,
                "scene_id": prov.scene_id,
                "kind": prov.kind.value,
                "path": prov.path,
                "approved": int(prov.approved),
                "data": self.db.dump(prov),
            },
        )
        if prov.path:
            p = Path(prov.path + ".prov.json")
            try:
                prov.write_json(str(p))
            except OSError:
                pass

    def get_asset_provenance(self, asset_id: str) -> AssetProvenance | None:
        row = self.db.query_one("SELECT data FROM assets WHERE asset_id=?", (asset_id,))
        if not row:
            return None
        return AssetProvenance.model_validate_json(row["data"])

    def assets_for_episode(self, episode_id: str, kind: str | None = None) -> list[sqlite3.Row]:
        if kind:
            return self.db.query_all(
                "SELECT * FROM assets WHERE episode_id=? AND kind=? ORDER BY asset_id",
                (episode_id, kind),
            )
        return self.db.query_all(
            "SELECT * FROM assets WHERE episode_id=? ORDER BY asset_id", (episode_id,)
        )

    def save_qc_result(self, episode_id, scene_id, target_path, category, passed, details) -> None:
        self.db.execute(
            "INSERT INTO qc_results (episode_id, scene_id, target_path, category, passed, details)"
            " VALUES (?,?,?,?,?,?)",
            (episode_id, scene_id, target_path, category, int(passed), json.dumps(details)),
        )

    def gate_status(self, gate_id: int, episode_id: str) -> dict[str, Any] | None:
        row = self.db.query_one(
            "SELECT * FROM gates WHERE gate_id=? AND episode_id=?", (gate_id, episode_id)
        )
        return dict(row) if row else None

    def set_gate(self, gate_id: int, episode_id: str, status: str, note: str, approver: str) -> None:
        self.db.execute(
            "INSERT INTO gates (gate_id, episode_id, status, note, approver) VALUES (?,?,?,?,?) "
            "ON CONFLICT(gate_id, episode_id) DO UPDATE SET status=excluded.status,"
            " note=excluded.note, approver=excluded.approver, decided_at=CURRENT_TIMESTAMP",
            (gate_id, episode_id, status, note, approver),
        )

    def save_render(self, render_id, episode_id, mode, path, qc_state, duration) -> None:
        self.db.upsert(
            "renders",
            "render_id",
            {
                "render_id": render_id,
                "episode_id": episode_id,
                "mode": mode,
                "path": path or "",
                "qc_state": qc_state,
                "duration": duration,
            },
        )
