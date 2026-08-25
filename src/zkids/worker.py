from __future__ import annotations

import json
import os
import sys

from .infrastructure import RedisQueue


def run_once() -> bool:
    url = os.getenv("REDIS_URL")
    if not url:
        raise RuntimeError("REDIS_URL is required")
    queue = RedisQueue(url)
    message = queue.lease(timeout_seconds=1)
    if message is None:
        return False
    print(json.dumps({"event": "job.leased", "job_id": message.job_id}, sort_keys=True))
    return True


def main() -> int:
    while True:
        run_once()


if __name__ == "__main__":
    sys.exit(main())
