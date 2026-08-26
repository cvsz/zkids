from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .logging import get_logger

log = get_logger("zkid.obs")

_START = time.monotonic()
_REQUESTS = {"total": 0, "4xx": 0, "5xx": 0}
_LATENCIES: list[float] = []

def record_request(status: int, latency_sec: float) -> None:
    _REQUESTS["total"] += 1
    if 400 <= status < 500:
        _REQUESTS["4xx"] += 1
    if status >= 500:
        _REQUESTS["5xx"] += 1
    _LATENCIES.append(latency_sec)
    if len(_LATENCIES) > 1000:
        _LATENCIES.pop(0)

def prometheus_metrics() -> str:
    uptime = time.monotonic() - _START
    avg_lat = sum(_LATENCIES) / len(_LATENCIES) if _LATENCIES else 0
    p95 = sorted(_LATENCIES)[int(len(_LATENCIES) * 0.95)] if _LATENCIES else 0
    lines = [
        "# HELP zkid_uptime_seconds Uptime",
        "# TYPE zkid_uptime_seconds gauge",
        f"zkid_uptime_seconds {uptime:.1f}",
        "# HELP zkid_requests_total Total requests",
        "# TYPE zkid_requests_total counter",
        f"zkid_requests_total { _REQUESTS['total']}",
        "# HELP zkid_requests_4xx 4xx",
        f"zkid_requests_4xx { _REQUESTS['4xx']}",
        "# HELP zkid_requests_5xx 5xx",
        f"zkid_requests_5xx { _REQUESTS['5xx']}",
        "# HELP zkid_latency_avg Average latency",
        f"zkid_latency_avg {avg_lat:.4f}",
        "# HELP zkid_latency_p95 p95",
        f"zkid_latency_p95 {p95:.4f}",
    ]
    # DB size
    try:
        from .config import FactoryConfig
        cfg = FactoryConfig.load(Path.cwd())
        if cfg.db_path.exists():
            lines.append(f"zkid_db_size_bytes {cfg.db_path.stat().st_size}")
    except Exception:
        pass
    return "\n".join(lines) + "\n"

def health_check(cfg=None) -> dict:
    checks = {}
    # DB
    try:
        from .config import FactoryConfig
        c = cfg or FactoryConfig.load(Path.cwd())
        checks["db"] = "ok" if c.db_path.exists() else "missing (will be created)"
    except Exception as e:
        checks["db"] = f"error: {e}"
    # ffmpeg
    try:
        import subprocess
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=3)
        checks["ffmpeg"] = "ok" if r.returncode == 0 else "missing"
    except Exception as e:
        checks["ffmpeg"] = f"error: {e}"
    # disk
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        checks["disk_free_gb"] = round(free / 1e9, 1)
        checks["disk"] = "ok" if free > 1e9 else "low"
    except Exception as e:
        checks["disk"] = f"error: {e}"
    # overall
    ok = all(v == "ok" or isinstance(v, (int, float)) for k, v in checks.items() if k not in ("disk_free_gb",))
    checks["status"] = "healthy" if ok else "degraded"
    checks["uptime_sec"] = round(time.monotonic() - _START, 1)
    return checks

def readiness_check(cfg=None) -> tuple[bool, dict]:
    h = health_check(cfg)
    ready = h.get("status") == "healthy" and h.get("db") in ("ok", "missing (will be created)")
    return ready, h
