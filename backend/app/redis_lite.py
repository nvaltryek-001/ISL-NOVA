"""Minimal Redis client (RESP2 over a socket, standard library only) plus the two
features ISL NOVA uses Redis for when REDIS_URL is set:

* ``RedisRateLimiter`` - one fixed-window counter per key shared by every API process
  (INCR + PEXPIRE in a pipeline); falls back to the in-process limiter if Redis is down.
* ``RedisJobs``        - a durable job list (LPUSH / BRPOP) consumed by ``python -m app.worker``,
  so training, evaluation and video analysis can run outside the API processes.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
import urllib.parse

log = logging.getLogger("isl_nova.redis")


class RedisError(RuntimeError):
    pass


class Redis:
    def __init__(self, url: str, timeout: float = 2.0):
        u = urllib.parse.urlsplit(url)
        if u.scheme not in ("redis", "rediss"):
            raise ValueError("REDIS_URL must start with redis://")
        if u.scheme == "rediss":
            raise ValueError("TLS (rediss://) is not supported by the built-in client; use a TLS proxy")
        self.host, self.port = u.hostname or "localhost", u.port or 6379
        self.password = urllib.parse.unquote(u.password) if u.password else None
        self.db = int((u.path or "/0").lstrip("/") or 0)
        self.timeout = timeout
        self._local = threading.local()

    # --- connection ---------------------------------------------------------
    def _conn(self):
        c = getattr(self._local, "c", None)
        if c is None:
            s = socket.create_connection((self.host, self.port), timeout=self.timeout)
            self._local.c = c = (s, s.makefile("rb"))
            if self.password:
                self._roundtrip(["AUTH", self.password])
            if self.db:
                self._roundtrip(["SELECT", str(self.db)])
        return c

    def close(self):
        c = getattr(self._local, "c", None)
        if c:
            try:
                c[0].close()
            finally:
                self._local.c = None

    @staticmethod
    def _encode(args) -> bytes:
        out = [f"*{len(args)}\r\n".encode()]
        for a in args:
            b = a if isinstance(a, bytes) else str(a).encode()
            out.append(f"${len(b)}\r\n".encode() + b + b"\r\n")
        return b"".join(out)

    def _read(self, f):
        line = f.readline()
        if not line:
            raise RedisError("connection closed")
        t, rest = line[:1], line[1:-2]
        if t == b"+":
            return rest.decode()
        if t == b"-":
            raise RedisError(rest.decode())
        if t == b":":
            return int(rest)
        if t == b"$":
            n = int(rest)
            if n == -1:
                return None
            data = f.read(n + 2)
            return data[:-2]
        if t == b"*":
            n = int(rest)
            return None if n == -1 else [self._read(f) for _ in range(n)]
        raise RedisError(f"bad reply {line!r}")

    def _roundtrip(self, *cmds, timeout: float | None = None):
        s, f = self._local.c
        if timeout is not None:
            s.settimeout(timeout)
        try:
            s.sendall(b"".join(self._encode(c) for c in cmds))
            return [self._read(f) for _ in cmds]
        finally:
            if timeout is not None:
                s.settimeout(self.timeout)

    def execute(self, *args, timeout: float | None = None):
        return self.pipeline([list(args)], timeout=timeout)[0]

    def pipeline(self, cmds, timeout: float | None = None):
        try:
            self._conn()
            return self._roundtrip(*cmds, timeout=timeout)
        except (OSError, RedisError):
            self.close()
            raise


class RedisRateLimiter:
    def __init__(self, redis: Redis, prefix: str = "isl-nova:rl:"):
        from .api import RateLimiter

        self.r, self.prefix = redis, prefix
        self.fallback = RateLimiter()
        self._warned = 0.0

    def check(self, key: str, limit: int, window: float = 60.0) -> bool:
        bucket = int(time.time() // window)
        k = f"{self.prefix}{key}:{bucket}"
        try:
            n, _ = self.r.pipeline([["INCR", k], ["PEXPIRE", k, int(window * 1000) + 1000]])
            return int(n) <= limit
        except (OSError, RedisError) as exc:
            if time.monotonic() - self._warned > 60:
                log.warning("redis unavailable for rate limiting, using the in-process limiter: %s", exc)
                self._warned = time.monotonic()
            return self.fallback.check(key, limit, window)


JOB_QUEUE = "isl-nova:jobs"


class RedisJobs:
    """Same submit() signature as services.Jobs; the job runs in a worker process."""

    def __init__(self, redis: Redis):
        self.r = redis

    def submit(self, fn, *args):
        from .jobs_registry import name_for

        state, *rest = args  # first argument is always the AppState; workers build their own
        self.r.execute("LPUSH", JOB_QUEUE, json.dumps({"job": name_for(fn), "args": rest, "queued_at": time.time()}))
        return None

    def shutdown(self):
        self.r.close()
