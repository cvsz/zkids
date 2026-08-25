from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class AuthError(ValueError):
    pass


class Role(StrEnum):
    VIEWER = "viewer"
    EDITOR = "editor"
    OPERATOR = "operator"
    PUBLISHER = "publisher"
    ADMIN = "admin"


PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.VIEWER: frozenset({"read"}),
    Role.EDITOR: frozenset({"read", "write"}),
    Role.OPERATOR: frozenset({"read", "write", "execute"}),
    Role.PUBLISHER: frozenset({"read", "write", "execute", "approve_publish"}),
    Role.ADMIN: frozenset({"read", "write", "execute", "approve_publish", "admin"}),
}


@dataclass(frozen=True, slots=True)
class Principal:
    subject: str
    tenant_id: str
    role: Role
    expires_at: int

    def require(self, permission: str) -> None:
        if permission not in PERMISSIONS[self.role]:
            raise AuthError(f"permission denied: {permission}")


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_token(
    *, subject: str, tenant_id: str, role: Role, ttl_seconds: int = 3600, secret: str | None = None
) -> str:
    key = secret or os.getenv("ZKIDS_AUTH_SECRET")
    if not key:
        raise AuthError("ZKIDS_AUTH_SECRET is required")
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "ZKIDS"}).encode("utf-8"))
    payload_obj = {
        "sub": subject,
        "tenant_id": tenant_id,
        "role": role.value,
        "exp": int(time.time()) + ttl_seconds,
    }
    payload = _b64encode(json.dumps(payload_obj, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = _b64encode(hmac.new(key.encode("utf-8"), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def verify_token(token: str, *, secret: str | None = None, now: int | None = None) -> Principal:
    key = secret or os.getenv("ZKIDS_AUTH_SECRET")
    if not key:
        raise AuthError("ZKIDS_AUTH_SECRET is required")
    try:
        header, payload, signature = token.split(".")
    except ValueError as exc:
        raise AuthError("invalid token format") from exc
    signing_input = f"{header}.{payload}".encode("ascii")
    expected = _b64encode(hmac.new(key.encode("utf-8"), signing_input, hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise AuthError("invalid token signature")
    try:
        data: dict[str, Any] = json.loads(_b64decode(payload))
        principal = Principal(
            subject=str(data["sub"]),
            tenant_id=str(data["tenant_id"]),
            role=Role(str(data["role"])),
            expires_at=int(data["exp"]),
        )
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise AuthError("invalid token payload") from exc
    current = int(time.time()) if now is None else now
    if principal.expires_at <= current:
        raise AuthError("token expired")
    return principal
