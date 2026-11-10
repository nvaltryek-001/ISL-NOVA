"""Background worker for the Redis job queue.

    REDIS_URL=redis://localhost:6379/0 python -m app.worker

Runs training, evaluation and video-analysis jobs queued by API processes (with
REDIS_URL set, the API queues them instead of running them in-process). Several
workers may run at once; each job is taken by exactly one (BRPOP).
"""

from __future__ import annotations

import json
import logging
import signal

from .config import Settings
from .jobs_registry import get
from .redis_lite import JOB_QUEUE, Redis, RedisError

log = logging.getLogger("isl_nova.worker")


def run(max_jobs: int | None = None, block_seconds: int = 5) -> int:
    from .main import AppState

    settings = Settings.from_env()
    if not settings.redis_url:
        raise SystemExit("REDIS_URL is not set")
    state = AppState(settings)
    state.startup()
    r = Redis(settings.redis_url, timeout=block_seconds + 5)
    done, stop = 0, False

    def _stop(*_):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log.info("worker started, queue %s", JOB_QUEUE)
    while not stop and (max_jobs is None or done < max_jobs):
        try:
            item = r.execute("BRPOP", JOB_QUEUE, block_seconds, timeout=block_seconds + 5)
        except (OSError, RedisError) as exc:
            log.warning("redis error: %s", exc)
            continue
        if not item:
            continue
        msg = json.loads(item[1])
        try:
            get(msg["job"])(state, *msg["args"])
            log.info("job %s %s done", msg["job"], msg["args"])
        except Exception:  # noqa: BLE001 - one bad job must not stop the worker
            log.exception("job %s failed", msg)
        done += 1
    return done


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
