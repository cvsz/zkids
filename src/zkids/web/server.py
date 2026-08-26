from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ..config import FactoryConfig
from ..logging import get_logger
from .. import observability as obs
from .. import security as sec

log = get_logger("zkid.web")

MAX_LOG_TAIL_BYTES = 8000


@dataclass
class ProduceTask:
    task_id: str
    topic: str
    episode_id: str | None
    draft: bool
    auto_approve: bool
    state: str = "running"
    returncode: int | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    log_path: str = ""


class TaskRegistry:
    def __init__(self, max_keep: int = 30) -> None:
        self._tasks: dict[str, ProduceTask] = {}
        self._lock = threading.Lock()
        self._max_keep = max_keep

    def add(self, task: ProduceTask) -> None:
        with self._lock:
            self._tasks[task.task_id] = task
            if len(self._tasks) > self._max_keep:
                oldest = sorted(self._tasks.items(), key=lambda kv: kv[1].started_at)[0][0]
                self._tasks.pop(oldest, None)

    def get(self, task_id: str) -> ProduceTask | None:
        return self._tasks.get(task_id)

    def all(self) -> list[ProduceTask]:
        return sorted(self._tasks.values(), key=lambda t: -t.started_at)


def _safe_join(base: Path, relative: str) -> Path | None:
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError:
        return None
    return candidate


def _tail(path: Path, limit: int = MAX_LOG_TAIL_BYTES) -> str:
    try:
        data = path.read_bytes()
        return data[-limit:].decode("utf-8", errors="replace")
    except OSError:
        return ""


class ZkidWebServer:
    def __init__(self, cfg: FactoryConfig, token: str | None, venv_python: Path | None = None) -> None:
        self.cfg = cfg
        self.token = token
        self.registry = TaskRegistry()
        self.python = venv_python or Path(__file__).parents[3] / ".venv" / "bin" / "python"

    def episodes(self, search: str | None = None) -> list[dict]:
        if not self.cfg.db_path.exists():
            return []
        import sqlite3
        out: list[dict] = []
        conn = sqlite3.connect(f"file:{self.cfg.db_path}?mode=ro", uri=True)
        try:
            sql = "SELECT e.episode_id, e.title, e.state, e.data, (SELECT COUNT(*) FROM generation_jobs j WHERE j.episode_id=e.episode_id) AS jobs FROM episodes e"
            params = ()
            if search:
                sql += " WHERE e.episode_id LIKE ? OR e.title LIKE ?"
                params = (f"%{search}%", f"%{search}%")
            sql += " ORDER BY e.created_at DESC"
            cur = conn.execute(sql, params)
            for r in cur.fetchall():
                try:
                    data = json.loads(r[3]) if r[3] else {}
                except Exception:
                    data = {}
                out.append({"episode_id": r[0], "title": r[1], "state": r[2], "jobs": r[4], "learning_goal": data.get("learning_goal"), "topic": data.get("topic")})
        finally:
            conn.close()
        return out

    def status(self, episode_id: str) -> dict | None:
        from ..db import Database, FactoryRepository
        if not self.cfg.db_path.exists():
            return None
        db = Database(self.cfg.db_path)
        repo = FactoryRepository(db)
        script = repo.get_episode_script(episode_id)
        if not script:
            db.close()
            return None
        jobs = repo.jobs_for_episode(episode_id)
        counts: dict[str, int] = {}
        for j in jobs:
            counts[j.state.value] = counts.get(j.state.value, 0) + 1
        used = db.query_one(
            "SELECT SUM(CASE WHEN kind='STILL' THEN 1 ELSE 0 END) AS imgs,"
            "SUM(CASE WHEN kind='VIDEO' THEN 1 ELSE 0 END) AS vids,"
            "COALESCE(SUM(cost_estimate_usd),0) AS cost FROM generation_jobs WHERE episode_id=?",
            (episode_id,),
        )
        renders = [dict(r) for r in db.query_all("SELECT mode, qc_state, path, duration, created_at FROM renders WHERE episode_id=? ORDER BY created_at DESC LIMIT 5", (episode_id,))]
        from ..pipeline.gates import GateKeeper
        gates = GateKeeper(repo).status_all(episode_id)
        db.close()
        budget_cfg = self.cfg.budgets
        return {
            "episode_id": episode_id,
            "title": script.title,
            "scenes": len(script.scenes),
            "learning_goal": script.learning_goal,
            "topic": script.topic,
            "gates": gates,
            "jobs": {"total": len(jobs), "by_state": counts},
            "budget": {"images_used": used["imgs"] or 0, "images_limit": budget_cfg.image_generations, "videos_used": used["vids"] or 0, "videos_limit": budget_cfg.video_generations, "cost_usd": round(used["cost"] or 0.0, 2), "cost_limit_usd": budget_cfg.max_cost_usd_per_episode},
            "renders": renders,
        }

    def detail(self, episode_id: str) -> dict | None:
        from ..db import Database, FactoryRepository
        if not self.cfg.db_path.exists():
            return None
        db = Database(self.cfg.db_path)
        repo = FactoryRepository(db)
        script = repo.get_episode_script(episode_id)
        if not script:
            db.close()
            return None
        sb = repo.get_storyboard(episode_id)
        manifest = repo.get_manifest(episode_id)
        tl_path = self.cfg.episode_dir(episode_id) / "metadata" / "timeline.json"
        timeline = None
        if tl_path.exists():
            try:
                timeline = json.loads(tl_path.read_text(encoding="utf-8"))
            except Exception:
                timeline = None
        qc_rows = db.query_all("SELECT category, passed, details, target_path, created_at FROM qc_results WHERE episode_id=? ORDER BY created_at DESC LIMIT 80", (episode_id,))
        qc = [{"category": r["category"], "passed": bool(r["passed"]), "details": json.loads(r["details"] or "{}"), "target": r["target_path"]} for r in qc_rows]
        job_rows = db.query_all("SELECT job_id, kind, scene_id, state, attempts, max_retries, provider, error, artifacts FROM generation_jobs WHERE episode_id=? ORDER BY job_id", (episode_id,))
        jobs = [{"job_id": r["job_id"], "kind": r["kind"], "scene_id": r["scene_id"], "state": r["state"], "attempts": r["attempts"], "max_retries": r["max_retries"], "provider": r["provider"], "error": r["error"], "artifacts": json.loads(r["artifacts"] or "[]")} for r in job_rows]
        assets = []
        for row in db.query_all("SELECT asset_id, kind, scene_id, path, approved, data FROM assets WHERE episode_id=? ORDER BY asset_id", (episode_id,)):
            try:
                prov = json.loads(row["data"])
            except Exception:
                prov = {}
            assets.append({"asset_id": row["asset_id"], "kind": row["kind"], "scene_id": row["scene_id"], "path": row["path"], "approved": bool(row["approved"]), "provenance": prov})
        db.close()
        stills = []
        stills_dir = self.cfg.episode_dir(episode_id) / "stills"
        for p in sorted(stills_dir.glob("*.png")):
            prov_path = p.with_suffix(".png.prov.json")
            if not prov_path.exists():
                prov_path = Path(str(p) + ".prov.json")
            prov = None
            if prov_path.exists():
                try:
                    prov = json.loads(prov_path.read_text(encoding="utf-8"))
                except Exception:
                    prov = None
            rel = p.relative_to(self.cfg.episodes_dir).as_posix()
            stills.append({"file": rel, "prov": prov})
        videos = []
        vdir = self.cfg.episode_dir(episode_id) / "video"
        for p in sorted(vdir.glob("**/*.mp4")):
            rel = p.relative_to(self.cfg.episodes_dir).as_posix()
            videos.append({"file": rel})
        subs = []
        for p in sorted((self.cfg.episode_dir(episode_id) / "subtitles").glob("*.srt")):
            try:
                subs.append({"file": p.relative_to(self.cfg.episodes_dir).as_posix(), "size": p.stat().st_size})
            except OSError:
                pass
        return {"script": json.loads(script.model_dump_json()), "storyboard": json.loads(sb.model_dump_json()) if sb else None, "manifest": json.loads(manifest.model_dump_json()) if manifest else None, "timeline": timeline, "qc": qc, "jobs": jobs, "assets": assets, "stills": stills, "videos": videos, "subtitles": subs}

    def get_series(self) -> dict | None:
        from ..models import SeriesBible
        path = self.cfg.templates_dir / "series-bible.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        from ..db import Database, FactoryRepository
        if self.cfg.db_path.exists():
            db = Database(self.cfg.db_path)
            repo = FactoryRepository(db)
            rows = db.query_all("SELECT data FROM series LIMIT 1")
            db.close()
            if rows:
                try:
                    return json.loads(rows[0]["data"])
                except Exception:
                    return None
        return None

    def put_series(self, payload: dict) -> tuple[bool, str]:
        from ..models import SeriesBible
        try:
            bible = SeriesBible.model_validate(payload)
        except Exception as e:
            return False, str(e)
        path = self.cfg.templates_dir / "series-bible.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(bible.model_dump_json(indent=2), encoding="utf-8")
        try:
            from ..db import Database, FactoryRepository
            db = Database(self.cfg.db_path)
            repo = FactoryRepository(db)
            repo.save_series(bible)
            db.close()
        except Exception:
            pass
        return True, ""

    def list_characters(self) -> list[dict]:
        out = []
        for p in sorted((self.cfg.templates_dir / "characters").glob("*.json")):
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass
        if not out and self.cfg.db_path.exists():
            try:
                from ..db import Database, FactoryRepository
                db = Database(self.cfg.db_path)
                repo = FactoryRepository(db)
                chars = repo.get_characters_for_series()
                db.close()
                out = [json.loads(c.model_dump_json()) for c in chars]
            except Exception:
                pass
        return out

    def get_character(self, char_id: str) -> dict | None:
        for p in (self.cfg.templates_dir / "characters").glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get("character_id") == char_id:
                    return data
            except Exception:
                pass
        return None

    def put_character(self, char_id: str, payload: dict) -> tuple[bool, str]:
        from ..models import CharacterSpec
        payload = dict(payload)
        payload["character_id"] = char_id
        try:
            spec = CharacterSpec.model_validate(payload)
        except Exception as e:
            return False, str(e)
        path = self.cfg.templates_dir / "characters" / f"{char_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")
        try:
            from ..db import Database, FactoryRepository
            db = Database(self.cfg.db_path)
            repo = FactoryRepository(db)
            repo.save_character(spec)
            db.close()
        except Exception:
            pass
        return True, ""

    def create_character(self, payload: dict) -> tuple[dict | None, str]:
        from ..models import CharacterSpec
        try:
            spec = CharacterSpec.model_validate(payload)
        except Exception as e:
            return None, str(e)
        path = self.cfg.templates_dir / "characters" / f"{spec.character_id}.json"
        if path.exists():
            return None, "character_id already exists"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")
        try:
            from ..db import Database, FactoryRepository
            db = Database(self.cfg.db_path)
            repo = FactoryRepository(db)
            repo.save_character(spec)
            db.close()
        except Exception:
            pass
        return json.loads(spec.model_dump_json()), ""

    def delete_character(self, char_id: str) -> bool:
        path = self.cfg.templates_dir / "characters" / f"{char_id}.json"
        existed = path.exists()
        if existed:
            path.unlink()
        try:
            if self.cfg.db_path.exists():
                import sqlite3
                conn = sqlite3.connect(self.cfg.db_path)
                conn.execute("DELETE FROM characters WHERE character_id=?", (char_id,))
                conn.commit()
                conn.close()
        except Exception:
            pass
        return existed

    def list_assets_global(self, kind: str | None = None, provider: str | None = None, search: str | None = None, limit: int = 60, offset: int = 0) -> dict:
        if not self.cfg.db_path.exists():
            return {"assets": [], "total": 0}
        import sqlite3
        conn = sqlite3.connect(f"file:{self.cfg.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        where = []
        params: list = []
        if kind:
            where.append("kind=?")
            params.append(kind)
        if provider:
            where.append("data LIKE ?")
            params.append(f"%{provider}%")
        if search:
            where.append("(asset_id LIKE ? OR scene_id LIKE ? OR episode_id LIKE ?)")
            params.extend([f"%{search}%"]*3)
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        total = conn.execute(f"SELECT COUNT(*) FROM assets{where_sql}", params).fetchone()[0]
        rows = conn.execute(f"SELECT asset_id, episode_id, scene_id, kind, path, approved, data FROM assets{where_sql} ORDER BY asset_id DESC LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
        conn.close()
        assets = []
        for r in rows:
            try:
                prov = json.loads(r["data"])
            except Exception:
                prov = {}
            assets.append({"asset_id": r["asset_id"], "episode_id": r["episode_id"], "scene_id": r["scene_id"], "kind": r["kind"], "path": r["path"], "approved": bool(r["approved"]), "provenance": prov})
        return {"assets": assets, "total": total, "limit": limit, "offset": offset}

    def analytics_overview(self) -> dict:
        if not self.cfg.db_path.exists():
            return {"kpis": {}, "per_episode": []}
        import sqlite3
        conn = sqlite3.connect(f"file:{self.cfg.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        eps = conn.execute("SELECT episode_id, title, state, data FROM episodes").fetchall()
        total_cost = conn.execute("SELECT COALESCE(SUM(cost_estimate_usd),0) FROM generation_jobs").fetchone()[0] or 0
        total_jobs = conn.execute("SELECT COUNT(*) FROM generation_jobs").fetchone()[0] or 0
        failed = conn.execute("SELECT COUNT(*) FROM generation_jobs WHERE state IN ('FAILED','MANUAL_REVIEW')").fetchone()[0] or 0
        total_assets = conn.execute("SELECT COUNT(*) FROM assets WHERE kind IN ('video','still')").fetchone()[0] or 0
        conn.close()
        per_ep = []
        for r in eps:
            try:
                data = json.loads(r["data"]) if r["data"] else {}
            except Exception:
                data = {}
            eid = r["episode_id"]
            h = int(hashlib.sha256(eid.encode()).hexdigest()[:6], 16)
            per_ep.append({
                "episode_id": eid,
                "title": r["title"],
                "state": r["state"],
                "scenes": len(data.get("scenes") or []),
                "mock_ctr": round(2.5 + (h % 400)/100, 2),
                "mock_avg_view_sec": round(90 + (h % 120), 1),
                "mock_completion": round(55 + (h % 350)/10, 1),
                "mock_retention_drop_scene": (h % len(data.get("scenes") or [1])) + 1 if data.get("scenes") else None,
            })
        return {
            "kpis": {
                "episodes": len(eps),
                "total_jobs": total_jobs,
                "total_cost_usd": round(total_cost, 2),
                "avg_cost_per_episode": round(total_cost / max(len(eps),1), 2),
                "total_assets": total_assets,
                "failed_rate": round(failed / max(total_jobs,1) * 100, 1),
                "master_ready": sum(1 for r in eps if r["state"] == "master-ready"),
            },
            "per_episode": per_ep,
        }

    def retention_for(self, episode_id: str) -> dict | None:
        from ..db import Database, FactoryRepository
        if not self.cfg.db_path.exists():
            return None
        db = Database(self.cfg.db_path)
        repo = FactoryRepository(db)
        script = repo.get_episode_script(episode_id)
        db.close()
        if not script:
            return None
        h = int(hashlib.sha256(episode_id.encode()).hexdigest()[:8], 16)
        points = []
        retention = 100.0
        for i, s in enumerate(script.scenes):
            drop = (h >> (i*3) & 0x7) * 1.8 + (2 if s.segment in ("problem",) else 0)
            retention = max(28, retention - drop - (i*0.7))
            points.append({"scene_id": s.scene_id, "segment": s.segment, "retention": round(retention,1), "learning_point": s.learning_point})
        suggestion = "Dialog too long?" if min(p["retention"] for p in points) < 60 else "Pacing looks good; consider adding close-up on learning beat."
        return {"episode_id": episode_id, "points": points, "suggestion": suggestion}

    def free_catalog(self) -> dict:
        from ..free_env import get_free_catalog
        cat = get_free_catalog()
        # Annotate with has_key
        out = {}
        for kind, items in cat.items():
            out[kind] = []
            for it in items:
                has_key = True
                if it.get("env_key"):
                    has_key = bool(os.environ.get(it["env_key"]))
                    if not has_key and it.get("base_url", "").startswith("http://127.0.0.1"):
                        # offline local check
                        try:
                            import urllib.request
                            urllib.request.urlopen(it["base_url"].split("/v1")[0] + "/api/tags", timeout=2)
                            has_key = True
                        except Exception:
                            has_key = False
                out[kind].append({**it, "has_key": has_key, "env_value_present": bool(os.environ.get(it.get("env_key","") or ""))})
        return out

    def system_info(self) -> dict:
        info: dict = {"python": sys.version.split()[0], "providers": dict(self.cfg.providers), "baselines": {"master": {"width": self.cfg.master.width, "height": self.cfg.master.height, "fps": self.cfg.master.fps}, "draft": {"width": self.cfg.draft.width, "height": self.cfg.draft.height, "fps": self.cfg.draft.fps}}, "budgets": {"image_generations": self.cfg.budgets.image_generations, "video_generations": self.cfg.budgets.video_generations, "max_retries_per_scene": self.cfg.budgets.max_retries_per_scene, "max_cost_usd_per_episode": self.cfg.budgets.max_cost_usd_per_episode}}
        try:
            out = subprocess.run(["ffmpeg","-version"], capture_output=True, text=True, timeout=5)
            info["ffmpeg"] = (out.stdout or out.stderr or "").splitlines()[0][:120] if out.stdout or out.stderr else "not found"
        except Exception:
            info["ffmpeg"] = "not found"
        try:
            info["db_exists"] = self.cfg.db_path.exists()
            if self.cfg.db_path.exists():
                import sqlite3
                conn = sqlite3.connect(f"file:{self.cfg.db_path}?mode=ro", uri=True)
                info["db_tables"] = {r[0]: conn.execute(f"SELECT COUNT(*) FROM {r[0]}").fetchone()[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
                conn.close()
        except Exception as e:
            info["db_error"] = str(e)
        try:
            du = subprocess.run(["du","-sh", str(self.cfg.episodes_dir)], capture_output=True, text=True, timeout=5)
            info["episodes_disk"] = du.stdout.strip().split()[0] if du.stdout else "?"
        except Exception:
            info["episodes_disk"] = "?"
        return info

    def config_get(self) -> dict:
        env_overrides = {}
        try:
            from ..config import cfg_env_overrides
            env_overrides = cfg_env_overrides()
        except Exception:
            env_overrides = {}
        return {"providers": dict(self.cfg.providers), "providers_env_override": env_overrides, "budgets": {"image_generations": self.cfg.budgets.image_generations, "video_generations": self.cfg.budgets.video_generations, "max_retries_per_scene": self.cfg.budgets.max_retries_per_scene, "max_cost_usd_per_episode": self.cfg.budgets.max_cost_usd_per_episode}, "retry": {"max_attempts": self.cfg.retry.max_attempts, "escalation": {str(k): v for k, v in self.cfg.retry.escalation.items()}}, "audio": {"dialogue_lufs_target": self.cfg.audio.dialogue_lufs_target, "music_ducking_ratio": self.cfg.audio.music_ducking_ratio, "padding_after_voice_sec": self.cfg.audio.padding_after_voice_sec}, "auto_approve_in_draft": list(self.cfg.auto_approve_in_draft), "baselines": {"master": {"width": self.cfg.master.width, "height": self.cfg.master.height, "fps": self.cfg.master.fps}, "draft": {"width": self.cfg.draft.width, "height": self.cfg.draft.height, "fps": self.cfg.draft.fps}}}

    def config_put(self, payload: dict) -> tuple[bool, str]:
        import yaml
        cfg_path = self.cfg.root / "config/factory.yaml"
        try:
            raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
            if not isinstance(raw, dict):
                raw = {}
        except Exception as e:
            return False, f"read config failed: {e}"
        allowed_providers = {
            "llm": {"offline", "openai_compat", "ollama", "openrouter_free", "groq_free", "hf_free", "gemini_free", "zai_free", "together_free", "nvidia_free", "opencode_free", "kilocode_free", "meta_free", "free"},
            "image": {"placeholder", "procedural_cartoon", "pollinations", "hf_image", "hf_free", "google_imagen"},
            "voice": {"silent", "edge_tts", "google_tts"},
            "music": {"procedural"},
            "motion": {"kenburns", "veo"},
        }
        if "providers" in payload:
            prov = payload["providers"]
            if not isinstance(prov, dict):
                return False, "providers must be object"
            raw.setdefault("providers", {})
            for k, v in prov.items():
                if k not in allowed_providers:
                    return False, f"unknown provider {k}"
                if v not in allowed_providers[k]:
                    return False, f"invalid value {v} for {k}"
                raw["providers"][k] = v
        if "budgets" in payload:
            b = payload["budgets"]
            raw.setdefault("budgets", {})
            for k in ("image_generations", "video_generations", "max_retries_per_scene"):
                if k in b:
                    try:
                        raw["budgets"][k] = int(b[k])
                    except Exception:
                        return False, f"invalid int for budgets.{k}"
                    if raw["budgets"][k] < 1 or raw["budgets"][k] > 200:
                        return False, f"budgets.{k} out of range 1-200"
            if "max_cost_usd_per_episode" in b:
                try:
                    raw["budgets"]["max_cost_usd_per_episode"] = float(b["max_cost_usd_per_episode"])
                except Exception:
                    return False, "invalid max_cost_usd_per_episode"
        if "audio" in payload:
            a = payload["audio"]
            raw.setdefault("audio", {})
            for k in ("dialogue_lufs_target", "music_ducking_ratio", "padding_after_voice_sec"):
                if k in a:
                    try:
                        raw["audio"][k] = float(a[k])
                    except Exception:
                        return False, f"invalid float for audio.{k}"
        if "baselines" in payload:
            bl = payload["baselines"]
            if "master" in bl:
                raw.setdefault("master_baseline", {}).setdefault("video", {})
                raw.setdefault("master_baseline", {}).setdefault("audio", {})
                m = bl["master"]
                for k in ("width", "height", "fps"):
                    if k in m:
                        raw["master_baseline"]["video"][k] = int(m[k])
            if "draft" in bl:
                raw.setdefault("draft_baseline", {})
                for k in ("width", "height", "fps"):
                    if k in bl["draft"]:
                        raw["draft_baseline"][k] = int(bl["draft"][k])
        if "auto_approve_in_draft" in payload:
            v = payload["auto_approve_in_draft"]
            if not isinstance(v, list) or any(int(x) not in (1,2,3,4,5) for x in v):
                return False, "auto_approve_in_draft must be list of 1-5"
            raw.setdefault("gates", {})["auto_approve_in_draft"] = [int(x) for x in v]
        if "retry" in payload:
            r = payload["retry"]
            if "max_attempts" in r:
                raw.setdefault("retry_policy", {})["max_attempts"] = int(r["max_attempts"])
        try:
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            cfg_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
            self.cfg = FactoryConfig.load(self.cfg.root)
        except Exception as e:
            return False, str(e)
        return True, ""

    def gate_action(self, episode_id: str, gate_id: int, action: str, note: str, approver: str = "web") -> tuple[bool, str]:
        from ..db import Database, FactoryRepository
        from ..pipeline.gates import GateKeeper
        db = Database(self.cfg.db_path)
        repo = FactoryRepository(db)
        keeper = GateKeeper(repo)
        if action == "approve":
            keeper.approve(gate_id, episode_id, note=note, approver=approver)
            db.close()
            return True, ""
        if action == "reject":
            keeper.reject(gate_id, episode_id, note=note, approver=approver)
            db.close()
            return True, ""
        db.close()
        return False, "unknown action"

    def spawn_produce(self, payload: dict) -> tuple[ProduceTask | None, str]:
        if not self.token:
            return None, "mutations disabled: set ZKID_WEB_TOKEN to allow produce runs"
        topic = str(payload.get("topic") or "").strip()
        if not topic:
            return None, "topic is required"
        ep = payload.get("ep")
        if ep and not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", str(ep)):
            return None, "invalid episode id"
        task = ProduceTask(
            task_id=uuid.uuid4().hex[:12],
            topic=topic,
            episode_id=str(ep) if ep else None,
            draft=bool(payload.get("draft", True)),
            auto_approve=bool(payload.get("auto_approve", False)),
        )
        log_dir = self.cfg.root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"produce-{task.task_id}.log"
        task.log_path = str(log_path)
        cmd = [str(self.python), "-m", "zkid.cli", "--root", str(self.cfg.root), "produce", "--topic", topic, "--offline"]
        if task.draft:
            cmd.append("--draft")
        else:
            cmd.append("--production")
        if task.auto_approve:
            cmd.append("--auto-approve")
        if task.episode_id:
            cmd += ["--ep", task.episode_id]
        with log_path.open("w", encoding="utf-8") as lf:
            proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, cwd=str(self.cfg.root))
        def _wait() -> None:
            rc = proc.wait()
            task.returncode = rc
            task.state = "done" if rc == 0 else "failed"
            task.finished_at = time.time()
        threading.Thread(target=_wait, daemon=True).start()
        self.registry.add(task)
        return task, ""

    def task_payload(self, task: ProduceTask) -> dict:
        return {"task_id": task.task_id, "topic": task.topic, "episode_id": task.episode_id, "state": task.state, "returncode": task.returncode, "log_tail": _tail(Path(task.log_path)) if task.log_path else ""}


def _client_ip(handler: BaseHTTPRequestHandler) -> str:
    return handler.headers.get("X-Forwarded-For", handler.client_address[0]).split(",")[0].strip()

def _request_id() -> str:
    return uuid.uuid4().hex[:12]

OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {"title": "zkid Factory OS", "version": "0.1.0", "description": "Enterprise-grade kids cartoon factory — versioned, audited, rate-limited"},
    "servers": [{"url": "https://zkids.zeaz.dev"}, {"url": "http://127.0.0.1:8010"}],
    "paths": {
        "/api/health": {"get": {"summary": "Liveness probe", "responses": {"200": {"description": "ok"}}}},
        "/api/ready": {"get": {"summary": "Readiness probe (DB + ffmpeg)", "responses": {"200": {"description": "ready"}, "503": {"description": "not ready"}}}},
        "/metrics": {"get": {"summary": "Prometheus metrics", "responses": {"200": {"description": "text"}}}},
        "/openapi.json": {"get": {"summary": "OpenAPI spec", "responses": {"200": {"description": "spec"}}}},
        "/api/v1/episodes": {"get": {"summary": "List episodes (versioned)"}},
    },
}

def make_handler(app: ZkidWebServer, static_index: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "zkid-web/0.1"
        def log_message(self, fmt: str, *args) -> None:
            log.debug(fmt % args)
        def _add_security_headers(self):
            for k, v in sec.SECURITY_HEADERS.items():
                self.send_header(k, v)
            self.send_header("X-Request-Id", getattr(self, "_req_id", _request_id()))
        def _json(self, obj, code: int = 200) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self._add_security_headers()
            self.end_headers()
            self.wfile.write(body)
        def _authorized(self) -> bool:
            if not self.app.token:
                return False
            tok = self.headers.get("X-Auth-Token") or self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            # Try JWT first, fallback to legacy single token
            principal = sec.principal_from_token(tok)
            if principal:
                self._principal = principal
                return True
            # Legacy direct compare
            return tok == self.app.token
        def _require_role(self, role: str) -> bool:
            principal = getattr(self, "_principal", None)
            if not principal:
                tok = self.headers.get("X-Auth-Token") or self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
                principal = sec.principal_from_token(tok)
                self._principal = principal
            if not principal:
                # Fallback to legacy operator if token matches
                if (self.headers.get("X-Auth-Token") or "") == self.app.token:
                    return role in ("viewer", "operator")
                return False
            return principal.can(role)
        def _check_rate_limit(self) -> bool:
            ip = _client_ip(self)
            key = f"{ip}:{self.path.split('?')[0]}"
            if not sec.limiter.allow(key):
                self._json({"error": "rate limit exceeded", "retry_after": 1}, 429)
                return False
            return True
        def _read_json(self, limit: int = 50000) -> tuple[dict | None, str]:
            length = min(int(self.headers.get("Content-Length") or 0), limit)
            raw = self.rfile.read(length) if length else b"{}"
            if not raw:
                return {}, ""
            # Basic size check
            if len(raw) > limit:
                return None, "payload too large"
            try:
                data = json.loads(raw)
                # Prevent prototype pollution style keys
                if isinstance(data, dict) and any(k.startswith("__") for k in data.keys()):
                    return None, "invalid keys"
                return data, ""
            except json.JSONDecodeError as e:
                return None, str(e)
        def do_GET(self) -> None:
            self._req_id = _request_id()
            start = time.monotonic()
            if not self._check_rate_limit():
                obs.record_request(429, time.monotonic() - start)
                return
            parsed = urlparse(self.path)
            # Versioned alias: /api/v1/* -> /api/*
            path = parsed.path
            if path.startswith("/api/v1/"):
                path = "/api/" + path[len("/api/v1/"):]
                parsed = parsed._replace(path=path)
            qs = parse_qs(parsed.query)
            if path in ("/", "/index.html"):
                body = static_index.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self._add_security_headers()
                self.end_headers()
                self.wfile.write(body)
                obs.record_request(200, time.monotonic() - start)
                return
            if path in ("/api/health", "/health", "/healthz"):
                h = obs.health_check(app.cfg)
                h["ok"] = h.get("status") == "healthy"
                h["version"] = "0.1"
                code = 200 if h.get("status") == "healthy" else 503
                self._json(h, code)
                obs.record_request(code, time.monotonic() - start)
                return
            if path in ("/api/ready", "/ready"):
                ready, info = obs.readiness_check(app.cfg)
                self._json(info, 200 if ready else 503)
                obs.record_request(200 if ready else 503, time.monotonic() - start)
                return
            if path in ("/metrics", "/api/metrics"):
                body = obs.prometheus_metrics().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4")
                self.send_header("Content-Length", str(len(body)))
                self._add_security_headers()
                self.end_headers()
                self.wfile.write(body)
                obs.record_request(200, time.monotonic() - start)
                return
            if path in ("/openapi.json", "/api/openapi.json"):
                self._json(OPENAPI_SPEC)
                obs.record_request(200, time.monotonic() - start)
                return
            if path == "/api/health":
                self._json({"ok": True, "version": "0.1"})
                obs.record_request(200, time.monotonic() - start)
                return
            if path == "/api/episodes":
                search = (qs.get("search") or qs.get("q") or [""])[0] or None
                self._json({"episodes": app.episodes(search=search)})
                return
            if path == "/api/status":
                ep = (qs.get("ep") or [""])[0]
                st = app.status(ep)
                self._json(st if st else {"error": f"unknown episode {ep}"}, 200 if st else 404)
                return
            if path == "/api/detail":
                ep = (qs.get("ep") or [""])[0]
                d = app.detail(ep)
                self._json(d if d else {"error": f"unknown episode {ep}"}, 200 if d else 404)
                return
            if path == "/api/tasks":
                self._json({"tasks": [app.task_payload(t) for t in app.registry.all()]})
                return
            if path == "/api/qc":
                ep = (qs.get("ep") or [""])[0]
                d = app.detail(ep)
                self._json({"qc": d["qc"]} if d else {"error": f"unknown episode {ep}"}, 200 if d else 404)
                return
            if path == "/api/series":
                s = app.get_series()
                self._json(s if s else {"error": "no series"})
                return
            if path == "/api/characters":
                self._json({"characters": app.list_characters()})
                return
            m = re.fullmatch(r"/api/characters/([A-Za-z0-9_-]+)", path)
            if m:
                c = app.get_character(m.group(1))
                self._json(c if c else {"error": "not found"}, 200 if c else 404)
                return
            if path == "/api/assets":
                self._json(app.list_assets_global(kind=(qs.get("kind") or [None])[0], provider=(qs.get("provider") or [None])[0], search=(qs.get("search") or [None])[0], limit=int((qs.get("limit") or ["60"])[0]), offset=int((qs.get("offset") or ["0"])[0])))
                return
            m = re.fullmatch(r"/api/assets/([^/]+)", path)
            if m:
                aid = m.group(1)
                data = app.list_assets_global(search=aid, limit=1)
                found = next((x for x in data["assets"] if x["asset_id"] == aid), None)
                self._json(found if found else {"error": "not found"}, 200 if found else 404)
                return
            if path == "/api/analytics/overview":
                self._json(app.analytics_overview())
                return
            if path == "/api/analytics/retention":
                ep = (qs.get("ep") or [""])[0]
                r = app.retention_for(ep)
                self._json(r if r else {"error": "unknown episode"}, 200 if r else 404)
                return
            if path == "/api/free/catalog":
                self._json(app.free_catalog())
                return
            if path == "/api/system/info":
                self._json(app.system_info())
                return
            if path == "/api/config":
                self._json(app.config_get())
                return
            if path == "/api/events":
                task_id = (qs.get("task") or [""])[0]
                task = app.registry.get(task_id) if task_id else None
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                for _ in range(30):
                    payload = app.task_payload(task) if task else {"state": "missing"}
                    msg = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    try:
                        self.wfile.write(msg.encode())
                        self.wfile.flush()
                    except BrokenPipeError:
                        return
                    if task and task.state != "running":
                        return
                    time.sleep(1)
                return
            m = re.fullmatch(r"/api/tasks/([a-f0-9]{12})", path)
            if m:
                task = app.registry.get(m.group(1))
                self._json(app.task_payload(task) if task else {"error": "unknown task"}, 200 if task else 404)
                return
            m = re.fullmatch(r"/media/(.+)", path)
            if m:
                self._serve_media(m.group(1))
                return
            self._json({"error": "not found"}, 404)
        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            p = parsed.path
            if p == "/api/produce":
                payload, err = self._read_json()
                if err:
                    self._json({"error": err}, 400)
                    return
                if not self._authorized():
                    self._json({"error": "invalid or missing X-Auth-Token" if app.token else "mutations disabled: server has no ZKID_WEB_TOKEN configured"}, 403)
                    return
                task, e = app.spawn_produce(payload or {})
                self._json({"error": e}, 400) if e else self._json({"task": app.task_payload(task)}, 202)
                return
            if re.fullmatch(r"/api/gates/(approve|reject)", p):
                if not self._authorized():
                    self._json({"error": "invalid or missing X-Auth-Token" if app.token else "mutations disabled: server has no ZKID_WEB_TOKEN configured"}, 403)
                    return
                action = p.split("/")[-1]
                payload, err = self._read_json()
                if err:
                    self._json({"error": err}, 400)
                    return
                ep = str((payload or {}).get("ep") or "").strip()
                gate = (payload or {}).get("gate")
                note = str((payload or {}).get("note") or "")
                if not ep or gate not in (1,2,3,4,5):
                    self._json({"error": "ep and gate 1-5 required"}, 400)
                    return
                ok, e = app.gate_action(ep, int(gate), action, note)
                self._json({"error": e}, 400) if not ok else self._json({"ok": True, "gate": gate, "action": action})
                return
            if p == "/api/characters":
                if not self._authorized():
                    self._json({"error": "invalid or missing X-Auth-Token" if app.token else "mutations disabled"}, 403)
                    return
                payload, err = self._read_json(100000)
                if err or not payload:
                    self._json({"error": err or "body required"}, 400)
                    return
                data, e = app.create_character(payload)
                self._json({"error": e}, 400) if e else self._json(data, 201)
                return
            self._json({"error": "not found"}, 404)
        def do_PUT(self) -> None:
            parsed = urlparse(self.path)
            p = parsed.path
            if p == "/api/series":
                if not self._authorized():
                    self._json({"error": "invalid or missing X-Auth-Token" if app.token else "mutations disabled"}, 403)
                    return
                payload, err = self._read_json(50000)
                if err or payload is None:
                    self._json({"error": err or "body required"}, 400)
                    return
                ok, e = app.put_series(payload)
                self._json({"error": e}, 400) if not ok else self._json({"ok": True})
                return
            m = re.fullmatch(r"/api/characters/([A-Za-z0-9_-]+)", p)
            if m:
                if not self._authorized():
                    self._json({"error": "invalid or missing X-Auth-Token" if app.token else "mutations disabled"}, 403)
                    return
                payload, err = self._read_json(100000)
                if err or payload is None:
                    self._json({"error": err or "body required"}, 400)
                    return
                ok, e = app.put_character(m.group(1), payload)
                self._json({"error": e}, 400) if not ok else self._json({"ok": True})
                return
            if p == "/api/config":
                if not self._authorized():
                    self._json({"error": "invalid or missing X-Auth-Token" if app.token else "mutations disabled"}, 403)
                    return
                payload, err = self._read_json(50000)
                if err or payload is None:
                    self._json({"error": err or "body required"}, 400)
                    return
                ok, e = app.config_put(payload)
                self._json({"error": e}, 400) if not ok else self._json({"ok": True, "config": app.config_get()})
                return
            self._json({"error": "not found"}, 404)
        def do_DELETE(self) -> None:
            m = re.fullmatch(r"/api/characters/([A-Za-z0-9_-]+)", urlparse(self.path).path)
            if m:
                if not self._authorized():
                    self._json({"error": "invalid or missing X-Auth-Token" if app.token else "mutations disabled"}, 403)
                    return
                ok = app.delete_character(m.group(1))
                self._json({"ok": ok}, 200 if ok else 404)
                return
            self._json({"error": "not found"}, 404)
        def _serve_media(self, relpath: str) -> None:
            base = self.app.cfg.episodes_dir
            f = _safe_join(base, relpath)
            if not f or not f.is_file():
                self._json({"error": "not found"}, 404)
                return
            ctype = {".mp4": "video/mp4", ".png": "image/png", ".jpg": "image/jpeg", ".wav": "audio/wav", ".srt": "text/plain; charset=utf-8", ".json": "application/json"}.get(f.suffix, "application/octet-stream")
            size = f.stat().st_size
            rng = self.headers.get("Range")
            start, end = 0, size - 1
            code = 200
            if rng:
                m = re.match(r"bytes=(\d*)-(\d*)$", rng.strip())
                if m:
                    if m.group(1):
                        start = int(m.group(1))
                    if m.group(2):
                        end = min(int(m.group(2)), size - 1)
                    code = 206
            length = end - start + 1
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            if code == 206:
                self.send_header(f"Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            with f.open("rb") as fh:
                fh.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = fh.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
    Handler.app = app
    return Handler


def serve(host: str, port: int, root: Path, token: str | None) -> None:
    cfg = FactoryConfig.load(root)
    app = ZkidWebServer(cfg, token)
    index_path = Path(__file__).parent / "static" / "index.html"
    static_index = index_path.read_text(encoding="utf-8")
    handler = make_handler(app, static_index)
    httpd = ThreadingHTTPServer((host, port), handler)
    log.info("zkid web listening", extra={"stage": f"http://{host}:{port}"})
    httpd.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(prog="zkid-web")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--root", default=".")
    import os
    args = parser.parse_args()
    serve(args.host, args.port, Path(args.root).resolve(), os.environ.get("ZKID_WEB_TOKEN"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
