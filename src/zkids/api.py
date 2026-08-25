from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from .models import Episode, GenerationJob, Publication
from .runtime import SQLiteStore, TimelineItem, compile_timeline
from .states import EPISODE_TRANSITIONS, EpisodeState, assert_transition

app = FastAPI(title="zkids", version="0.1.0")
store = SQLiteStore(Path(".tmp/zkids.db"))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/validate")
def validate_contract(payload: dict[str, Any]) -> dict[str, Any]:
    kind = payload.get("kind")
    data = payload.get("data")
    if kind != "episode" or not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="supported kind: episode")
    try:
        episode = Episode.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    return {"valid": True, "episode_id": episode.episode_id}


@app.post("/v1/episodes")
def register_episode(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        episode = Episode.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    store.put_episode(episode.episode_id, episode.model_dump(mode="json"), EpisodeState.DRAFT)
    return {"episode_id": episode.episode_id, "state": EpisodeState.DRAFT.value}


@app.get("/v1/episodes/{episode_id}")
def get_episode(episode_id: str) -> dict[str, Any]:
    episode = store.get_episode(episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    return episode


@app.post("/v1/jobs")
def create_job(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        job = GenerationJob.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    return store.create_job(job.job_id, job.idempotency_key, job.model_dump(mode="json"))


@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    row = store.conn.execute(
        "SELECT job_id,payload,state,attempts FROM jobs WHERE job_id=?", (job_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    import json

    return {"job_id": row[0], "payload": json.loads(row[1]), "state": row[2], "attempts": row[3]}


@app.post("/v1/episodes/{episode_id}/gates/{gate}")
def approve_gate(episode_id: str, gate: str, payload: dict[str, Any]) -> dict[str, Any]:
    current = store.get_episode(episode_id)
    if current is None:
        raise HTTPException(status_code=404, detail="episode not found")
    if not payload.get("approved", False):
        raise HTTPException(status_code=400, detail="approval must be explicit")
    try:
        target = EpisodeState(gate)
        source = EpisodeState(current["state"])
        assert_transition(source, target, EPISODE_TRANSITIONS)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    episode_payload = {k: v for k, v in current.items() if k != "state"}
    store.put_episode(episode_id, episode_payload, target)
    store.audit("gate.approved", episode_id, {"gate": gate, "actor": payload.get("actor")})
    return {"episode_id": episode_id, "state": target.value}


@app.post("/v1/render/plan")
def render_plan(payload: dict[str, Any]) -> dict[str, Any]:
    items = [TimelineItem(**item) for item in payload.get("items", [])]
    return compile_timeline(items)


@app.post("/v1/publication/check")
def publication_check(payload: dict[str, Any]) -> dict[str, Any]:
    publication = Publication.model_validate(payload)
    try:
        publication.assert_publishable()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"publishable": True}
