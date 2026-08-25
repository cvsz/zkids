from __future__ import annotations

import json
import os
from html import escape
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

from .auth import AuthError, Principal, Role, verify_token
from .control_plane import ControlPlaneError, ControlPlaneService
from .models import Character, Episode, GenerationJob, Publication, QCResult
from .production import ProductionExecutor
from .providers import FakeProvider
from .runtime import SQLiteStore, TimelineItem, compile_timeline
from .states import EPISODE_TRANSITIONS, EpisodeState, JobState, assert_transition

app = FastAPI(title="zkids", version="1.0.0")
store = SQLiteStore(Path(".tmp/zkids.db"))
control = ControlPlaneService(store.conn)
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


def _episode_for(principal: Principal, episode_id: str) -> dict[str, Any]:
    episode = store.get_episode(episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    tenant_id = episode.get("tenant_id")
    if tenant_id is not None and tenant_id != principal.tenant_id and principal.role != Role.ADMIN:
        raise HTTPException(status_code=404, detail="episode not found")
    return episode


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, Any]:
    return {
        "status": "ready",
        "version": "1.0.0",
        "auth_enabled": bool(os.getenv("ZKIDS_AUTH_SECRET")),
        "database_backend": "sqlite" if not os.getenv("DATABASE_URL") else "postgresql-configured",
        "queue_backend": "local" if not os.getenv("REDIS_URL") else "redis-configured",
        "object_store": "local" if not os.getenv("S3_BUCKET") else "s3-configured",
        "publish_mode": "fake" if not os.getenv("ZKIDS_PUBLISH_ENDPOINT") else "external-configured",
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
    return _episode_for(principal, episode_id)


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
def get_job(job_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    principal = _require(authorization, "read")
    row = store.conn.execute(
        "SELECT job_id,payload,state,attempts FROM jobs WHERE job_id=?", (job_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    payload = dict(json.loads(row[1]))
    if payload.get("tenant_id") not in (None, principal.tenant_id) and principal.role != Role.ADMIN:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": row[0], "payload": payload, "state": row[2], "attempts": row[3]}


@app.post("/v1/jobs/{job_id}/retry")
def retry_job(job_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    principal = _require(authorization, "execute")
    row = store.conn.execute("SELECT payload,attempts FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    payload = dict(json.loads(row[0]))
    if payload.get("tenant_id") not in (None, principal.tenant_id) and principal.role != Role.ADMIN:
        raise HTTPException(status_code=404, detail="job not found")
    attempts = int(row[1]) + 1
    store.conn.execute(
        "UPDATE jobs SET state=?,attempts=? WHERE job_id=?", (JobState.RETRY.value, attempts, job_id)
    )
    store.conn.commit()
    store.audit("job.retry_requested", job_id, {"actor": principal.subject, "attempts": attempts})
    return {"job_id": job_id, "state": JobState.RETRY.value, "attempts": attempts}


@app.post("/v1/jobs/{job_id}/cancel")
def cancel_job(job_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    principal = _require(authorization, "execute")
    row = store.conn.execute("SELECT payload,state FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    payload = dict(json.loads(row[0]))
    if payload.get("tenant_id") not in (None, principal.tenant_id) and principal.role != Role.ADMIN:
        raise HTTPException(status_code=404, detail="job not found")
    store.conn.execute("UPDATE jobs SET state=? WHERE job_id=?", (JobState.CANCELLED.value, job_id))
    store.conn.commit()
    store.audit("job.cancelled", job_id, {"actor": principal.subject})
    return {"job_id": job_id, "state": JobState.CANCELLED.value}


@app.post("/v1/episodes/{episode_id}/gates/{gate}")
def approve_gate(
    episode_id: str,
    gate: str,
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    permission = "approve_publish" if gate == EpisodeState.HUMAN_PUBLISH_APPROVED.value else "write"
    principal = _require(authorization, permission)
    current = _episode_for(principal, episode_id)
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


@app.put("/v1/characters/{character_id}/versions/{version}")
def put_character_version(
    character_id: str,
    version: str,
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    principal = _require(authorization, "write")
    candidate = dict(payload)
    candidate["character_id"] = character_id
    candidate["version"] = version
    try:
        character = Character.model_validate(candidate)
        return control.put_character(principal.tenant_id, character.model_dump(mode="json"))
    except (ValidationError, ControlPlaneError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/v1/characters")
def list_character_versions(
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    principal = _require(authorization, "read")
    return control.list_characters(principal.tenant_id)


@app.put("/v1/episodes/{episode_id}/storyboard")
def put_storyboard(
    episode_id: str,
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    principal = _require(authorization, "write")
    _episode_for(principal, episode_id)
    try:
        return control.put_storyboard(principal.tenant_id, episode_id, payload)
    except ControlPlaneError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/v1/episodes/{episode_id}/storyboard")
def get_storyboard(
    episode_id: str, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    principal = _require(authorization, "read")
    _episode_for(principal, episode_id)
    result = control.latest_storyboard(principal.tenant_id, episode_id)
    if result is None:
        raise HTTPException(status_code=404, detail="storyboard not found")
    return result


@app.post("/v1/qc/reviews")
def create_qc_review(
    payload: dict[str, Any], authorization: str | None = Header(default=None)
) -> dict[str, str]:
    principal = _require(authorization, "write")
    try:
        result = QCResult.model_validate(payload)
        return control.review_qc(
            principal.tenant_id,
            result.entity_id,
            principal.subject,
            result.decision,
            str(payload.get("notes", "")),
        )
    except (ValidationError, ControlPlaneError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/analytics/events")
def ingest_analytics(
    payload: dict[str, Any], authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    principal = _require(authorization, "write")
    try:
        return control.ingest_analytics(principal.tenant_id, payload)
    except ControlPlaneError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/v1/analytics/episodes/{episode_id}/retention")
def episode_retention(
    episode_id: str, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    principal = _require(authorization, "read")
    _episode_for(principal, episode_id)
    return {"episode_id": episode_id, "scenes": control.scene_retention(principal.tenant_id, episode_id)}


@app.put("/v1/episodes/{episode_id}/variants/{variant_id}")
def put_episode_variant(
    episode_id: str,
    variant_id: str,
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    principal = _require(authorization, "write")
    _episode_for(principal, episode_id)
    candidate = dict(payload)
    candidate["variant_id"] = variant_id
    try:
        return control.put_variant(principal.tenant_id, episode_id, candidate)
    except ControlPlaneError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/episodes/{episode_id}/publish")
def publish_episode(
    episode_id: str,
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    principal = _require(authorization, "approve_publish")
    current = _episode_for(principal, episode_id)
    if current.get("state") != EpisodeState.HUMAN_PUBLISH_APPROVED.value:
        raise HTTPException(status_code=409, detail="HUMAN_PUBLISH_APPROVED gate is required")
    approved_by = str(payload.get("approved_by", "")).strip()
    if approved_by != principal.subject:
        raise HTTPException(status_code=409, detail="approved_by must match authenticated actor")
    try:
        result = control.publish_fake(
            principal.tenant_id,
            episode_id,
            idempotency_key=str(payload.get("idempotency_key", "")).strip(),
            destination=str(payload.get("destination", "youtube-dry-run")),
            approved=bool(payload.get("human_approved", False)),
            approved_by=approved_by,
            metadata=dict(payload.get("metadata", {})),
        )
    except ControlPlaneError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result.reused:
        episode_payload = {k: v for k, v in current.items() if k != "state"}
        store.put_episode(episode_id, episode_payload, EpisodeState.PUBLISHED)
        store.audit(
            "episode.published",
            episode_id,
            {
                "actor": principal.subject,
                "destination": result.destination,
                "publication_id": result.publication_id,
            },
        )
    return {
        "publication_id": result.publication_id,
        "external_id": result.external_id,
        "destination": result.destination,
        "reused": result.reused,
    }


@app.get("/control", response_class=HTMLResponse)
def control_plane_ui(authorization: str | None = Header(default=None)) -> HTMLResponse:
    principal = _require(authorization, "read")
    counts = control.dashboard(principal.tenant_id)
    cards = "".join(
        f"<article><strong>{escape(name.replace('_', ' ').title())}</strong><span>{value}</span></article>"
        for name, value in counts.items()
    )
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>zkids Control Plane</title><style>
body{{font-family:system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 20px;background:#10131a;color:#eef2ff}}
header{{display:flex;justify-content:space-between;align-items:end}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-top:24px}}
article{{background:#191f2b;border:1px solid #30394c;border-radius:14px;padding:20px;display:flex;justify-content:space-between;gap:12px}}span{{font-size:1.6rem}}code{{color:#a8c7fa}}
</style></head><body><header><div><h1>zkids Control Plane</h1><p>Character · Storyboard · Render · QC · Publish · Analytics</p></div><code>{escape(principal.tenant_id)}</code></header><main>{cards}</main></body></html>"""
    return HTMLResponse(html)
