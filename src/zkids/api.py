from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import ValidationError

from .auth import AuthError, Principal, Role, verify_token
from .models import Episode, GenerationJob, Publication
from .production import ProductionExecutor
from .providers import FakeProvider
from .runtime import SQLiteStore, TimelineItem, compile_timeline
from .states import EPISODE_TRANSITIONS, EpisodeState, assert_transition

app = FastAPI(title="zkids", version="0.2.0")
store = SQLiteStore(Path(".tmp/zkids.db"))
executor = ProductionExecutor()


def _principal(authorization: str | None) -> Principal:
    secret = os.getenv("ZKIDS_AUTH_SECRET")
    if not secret:
        return Principal(subject="offline", tenant_id="local", role=Role.ADMIN, expires_at=2**31)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="bearer token required")
    try:
        return verify_token(authorization.removeprefix("Bearer ").strip(), secret=secret)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _require(authorization: str | None, permission: str) -> Principal:
    principal = _principal(authorization)
    try:
        principal.require(permission)
    except AuthError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return principal


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, Any]:
    return {
        "status": "ready",
        "auth_enabled": bool(os.getenv("ZKIDS_AUTH_SECRET")),
        "database_backend": "sqlite" if not os.getenv("DATABASE_URL") else "postgresql-configured",
        "queue_backend": "local" if not os.getenv("REDIS_URL") else "redis-configured",
        "object_store": "local" if not os.getenv("S3_BUCKET") else "s3-configured",
    }


@app.get("/v1/auth/whoami")
def whoami(authorization: str | None = Header(default=None)) -> dict[str, str]:
    principal = _principal(authorization)
    return {
        "subject": principal.subject,
        "tenant_id": principal.tenant_id,
        "role": principal.role.value,
    }


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
def register_episode(
    payload: dict[str, Any], authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    principal = _require(authorization, "write")
    try:
        episode = Episode.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    data = episode.model_dump(mode="json")
    data["tenant_id"] = principal.tenant_id
    store.put_episode(episode.episode_id, data, EpisodeState.DRAFT)
    return {
        "episode_id": episode.episode_id,
        "tenant_id": principal.tenant_id,
        "state": EpisodeState.DRAFT.value,
    }


@app.get("/v1/episodes/{episode_id}")
def get_episode(
    episode_id: str, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    principal = _require(authorization, "read")
    episode = store.get_episode(episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    tenant_id = episode.get("tenant_id")
    if tenant_id is not None and tenant_id != principal.tenant_id and principal.role != Role.ADMIN:
        raise HTTPException(status_code=404, detail="episode not found")
    return episode


@app.post("/v1/jobs")
def create_job(
    payload: dict[str, Any], authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    principal = _require(authorization, "execute")
    try:
        job = GenerationJob.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    data = job.model_dump(mode="json")
    data["tenant_id"] = principal.tenant_id
    return store.create_job(job.job_id, f"{principal.tenant_id}:{job.idempotency_key}", data)


@app.get("/v1/jobs/{job_id}")
def get_job(
    job_id: str, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    principal = _require(authorization, "read")
    row = store.conn.execute(
        "SELECT job_id,payload,state,attempts FROM jobs WHERE job_id=?", (job_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    payload = json.loads(row[1])
    if payload.get("tenant_id") not in (None, principal.tenant_id) and principal.role != Role.ADMIN:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": row[0], "payload": payload, "state": row[2], "attempts": row[3]}


@app.post("/v1/episodes/{episode_id}/gates/{gate}")
def approve_gate(
    episode_id: str,
    gate: str,
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    permission = "approve_publish" if gate == EpisodeState.HUMAN_PUBLISH_APPROVED.value else "write"
    principal = _require(authorization, permission)
    current = store.get_episode(episode_id)
    if current is None:
        raise HTTPException(status_code=404, detail="episode not found")
    if current.get("tenant_id") not in (None, principal.tenant_id) and principal.role != Role.ADMIN:
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
    store.audit(
        "gate.approved",
        episode_id,
        {"gate": gate, "actor": principal.subject, "tenant_id": principal.tenant_id},
    )
    return {"episode_id": episode_id, "state": target.value}


@app.post("/v1/render/plan")
def render_plan(
    payload: dict[str, Any], authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    _require(authorization, "execute")
    items = [TimelineItem(**item) for item in payload.get("items", [])]
    return compile_timeline(items)


@app.post("/v1/providers/fake-generate")
def fake_generate(
    payload: dict[str, Any], authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    principal = _require(authorization, "execute")
    operation = str(payload.get("operation", "image"))
    cost_usd = float(payload.get("cost_usd", 0.0))
    result = executor.generate(
        tenant_id=principal.tenant_id,
        operation=operation,
        provider=FakeProvider(operation, cost_usd=cost_usd),
        request=dict(payload.get("request", {})),
        budget_limit=float(payload.get("budget_limit", 0.0)),
    )
    return {
        "provider": result.provider,
        "model": result.model,
        "asset_uri": result.asset_uri,
        "cost_usd": result.cost_usd,
    }


@app.post("/v1/publication/check")
def publication_check(
    payload: dict[str, Any], authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    _require(authorization, "approve_publish")
    publication = Publication.model_validate(payload)
    try:
        publication.assert_publishable()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"publishable": True}
