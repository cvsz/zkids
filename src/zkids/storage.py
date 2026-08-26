from __future__ import annotations

import os
from pathlib import Path

def get_s3_config() -> dict | None:
    endpoint = os.environ.get("S3_ENDPOINT") or os.environ.get("MINIO_ENDPOINT")
    if not endpoint:
        return None
    return {
        "endpoint": endpoint,
        "bucket": os.environ.get("S3_BUCKET", "zkid-assets"),
        "access_key": os.environ.get("S3_ACCESS_KEY"),
        "secret_key": os.environ.get("S3_SECRET_KEY"),
        "region": os.environ.get("S3_REGION", "us-east-1"),
    }

def is_s3_enabled() -> bool:
    return get_s3_config() is not None
