from __future__ import annotations

import os
from pathlib import Path

def get_postgres_dsn() -> str | None:
    return os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_DSN")

def is_postgres_enabled() -> bool:
    return bool(get_postgres_dsn())

def get_pool():
    dsn = get_postgres_dsn()
    if not dsn:
        return None
    try:
        import psycopg  # psycopg3
        return psycopg.connect(dsn)
    except ImportError:
        try:
            import psycopg2
            return psycopg2.connect(dsn)
        except ImportError:
            return None
    except Exception:
        return None
