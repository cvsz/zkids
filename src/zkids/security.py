from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .logging import get_logger

log = get_logger("zkid.security")

# ---- Roles ----
ROLES = {"viewer", "operator", "admin", "service"}
ROLE_HIERARCHY = {"viewer": 0, "operator": 1, "admin": 2, "service": 3}

# ---- Token handling (HMAC-based bearer, no external deps) ----
def _secret() -> str:
    # Prefer dedicated JWT secret, fallback to WEB_TOKEN, fallback to dev
    return os.environ.get("ZKID_JWT_SECRET") or os.environ.get("ZKID_WEB_TOKEN") or "dev-insecure-change-me"

def sign_token(payload: dict, ttl_sec: int = 3600) -> str:
    payload = dict(payload)
    payload["exp"] = int(time.time()) + ttl_sec
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    sig = hmac.new(_secret().encode(), body.encode(), hashlib.sha256).hexdigest()
    import base64
    b64 = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    return f"{b64}.{sig}"

def verify_token(token: str) -> Optional[dict]:
    try:
        import base64
        if "." not in token:
            # Legacy single-token mode: compare directly to WEB_TOKEN
            if token == os.environ.get("ZKID_WEB_TOKEN"):
                return {"sub": "operator", "role": "operator", "scope": "all"}
            return None
        b64, sig = token.rsplit(".", 1)
        # pad base64
        b64_padded = b64 + "=" * (-len(b64) % 4)
        body = base64.urlsafe_b64decode(b64_padded).decode()
        expected = hmac.new(_secret().encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        payload = json.loads(body)
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None

@dataclass
class Principal:
    sub: str
    role: str
    tenant: str = "default"
    scopes: list = None

    def can(self, required: str) -> bool:
        return ROLE_HIERARCHY.get(self.role, -1) >= ROLE_HIERARCHY.get(required, 99)

def principal_from_token(token: str | None) -> Optional[Principal]:
    if not token:
        return None
    # Support multi-tenant token via DB lookup or static map
    payload = verify_token(token)
    if not payload:
        return None
    return Principal(
        sub=payload.get("sub", "unknown"),
        role=payload.get("role", "viewer"),
        tenant=payload.get("tenant", "default"),
        scopes=payload.get("scopes") or [],
    )

# ---- Input validation ----
_MAX_TOPIC_LEN = 200
_MAX_ID_LEN = 32
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_SAFE_TOPIC_RE = re.compile(r"^[\w\s\-\.,!?'" + r'"]{1,200}$')

def validate_episode_id(ep: str) -> str:
    if not ep or not _SAFE_ID_RE.match(ep):
        raise ValueError("invalid episode id: must match [A-Za-z0-9_-]{1,32}")
    return ep

def validate_topic(topic: str) -> str:
    if not topic or len(topic) > _MAX_TOPIC_LEN:
        raise ValueError("topic required, max 200 chars")
    # Allow unicode letters, strip control chars
    if any(ord(c) < 32 for c in topic):
        raise ValueError("topic contains control characters")
    return topic.strip()

def sanitize_note(note: str) -> str:
    return (note or "")[:500].replace("\n", " ").strip()

# ---- Rate limiting (in-memory token bucket, with Redis fallback if available) ----
class RateLimiter:
    def __init__(self, rps: int = 10, burst: int = 20):
        self.rps = rps
        self.burst = burst
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_ts)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (self.burst, now))
        # refill
        elapsed = now - last
        tokens = min(self.burst, tokens + elapsed * self.rps)
        if tokens < 1:
            self._buckets[key] = (tokens, now)
            return False
        tokens -= 1
        self._buckets[key] = (tokens, now)
        return True

    def headers(self, key: str) -> dict:
        tokens, _ = self._buckets.get(key, (self.burst, time.monotonic()))
        return {"X-RateLimit-Remaining": str(int(tokens)), "X-RateLimit-Limit": str(self.burst)}

limiter = RateLimiter(rps=10, burst=30)

# ---- Audit log ----
def audit_log(db_path: Path, actor: str, action: str, target: str, tenant: str = "default", meta: dict | None = None) -> None:
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT DEFAULT CURRENT_TIMESTAMP, actor TEXT, action TEXT, target TEXT, tenant TEXT, meta TEXT)"
        )
        conn.execute(
            "INSERT INTO audit_log (actor, action, target, tenant, meta) VALUES (?,?,?,?,?)",
            (actor, action, target, tenant, json.dumps(meta or {})),
        )
        conn.commit()
        conn.close()
        log.info("audit", extra={"stage": f"{actor}:{action}:{target}"})
    except Exception as e:
        log.warning(f"audit log failed: {e}")

# ---- Security headers ----
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "0",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data: blob: https:; media-src 'self' blob: https:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self' https://api.meta.ai https://integrate.api.nvidia.com https://openrouter.ai",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}
