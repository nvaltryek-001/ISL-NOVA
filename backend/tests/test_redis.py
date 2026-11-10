"""Redis rate limiting and job queue.

A tiny in-process RESP server checks the protocol code everywhere; with
REDIS_TEST_URL set (CI service container) the same checks run against real Redis.
"""
import json
import os
import socketserver
import threading
from collections import defaultdict

import pytest
from app.redis_lite import JOB_QUEUE, Redis, RedisJobs, RedisRateLimiter


class _FakeRedis(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self):
        self.data = defaultdict(int)
        self.lists = defaultdict(list)
        super().__init__(("127.0.0.1", 0), _Handler)


class _Handler(socketserver.StreamRequestHandler):
    def _arg(self):
        n = int(self.rfile.readline()[1:])
        b = self.rfile.read(n + 2)[:-2]
        return b.decode()

    def handle(self):
        srv = self.server
        while True:
            line = self.rfile.readline()
            if not line:
                return
            args = [self._arg() for _ in range(int(line[1:]))]
            cmd = args[0].upper()
            if cmd in ("PING", "AUTH", "SELECT"):
                out = b"+OK\r\n"
            elif cmd == "INCR":
                srv.data[args[1]] += 1
                out = f":{srv.data[args[1]]}\r\n".encode()
            elif cmd == "PEXPIRE":
                out = b":1\r\n"
            elif cmd == "LPUSH":
                srv.lists[args[1]].insert(0, args[2])
                out = f":{len(srv.lists[args[1]])}\r\n".encode()
            elif cmd == "BRPOP":
                lst = srv.lists[args[1]]
                if lst:
                    v = lst.pop().encode()
                    k = args[1].encode()
                    out = b"*2\r\n" + f"${len(k)}\r\n".encode() + k + b"\r\n" + f"${len(v)}\r\n".encode() + v + b"\r\n"
                else:
                    out = b"*-1\r\n"
            else:
                out = f"-ERR unknown command {cmd}\r\n".encode()
            self.wfile.write(out)


@pytest.fixture(params=["fake", "real"])
def redis_url(request):
    if request.param == "real":
        url = os.environ.get("REDIS_TEST_URL")
        if not url:
            pytest.skip("set REDIS_TEST_URL to run against real Redis")
        r = Redis(url)
        r.execute("FLUSHDB")
        yield url
        return
    srv = _FakeRedis()
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"redis://127.0.0.1:{srv.server_address[1]}/0"
    srv.shutdown()


def test_shared_rate_limit_across_instances(redis_url):
    a, b = RedisRateLimiter(Redis(redis_url)), RedisRateLimiter(Redis(redis_url))  # two API processes
    got = [a.check("ip:1", 5), b.check("ip:1", 5), a.check("ip:1", 5), b.check("ip:1", 5), a.check("ip:1", 5)]
    assert all(got) and b.check("ip:1", 5) is False and a.check("ip:2", 5) is True


def test_rate_limiter_falls_back_when_redis_is_down():
    lim = RedisRateLimiter(Redis("redis://127.0.0.1:1/0", timeout=0.2))
    assert [lim.check("k", 2) for _ in range(3)] == [True, True, False]


def test_job_queue_round_trip(redis_url):
    from app.jobs_registry import get, name_for
    from app.routers.ml import _train_job

    r = Redis(redis_url)
    RedisJobs(r).submit(_train_job, object(), 42)
    item = r.execute("BRPOP", JOB_QUEUE, 1)
    msg = json.loads(item[1])
    assert msg["job"] == "train" and msg["args"] == [42] and get(name_for(_train_job)) is _train_job
    with pytest.raises(ValueError):
        name_for(print)


def test_redis_url_validation():
    with pytest.raises(ValueError):
        Redis("http://x")
    with pytest.raises(ValueError):
        Redis("rediss://x")


def test_api_queues_jobs_and_a_worker_runs_them(tmp_path, monkeypatch):
    """With REDIS_URL the API only queues the video-analysis job; `app.worker` runs it."""
    srv = _FakeRedis()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"redis://127.0.0.1:{srv.server_address[1]}/0"
    from app.main import create_app
    from starlette.testclient import TestClient

    from tests.conftest import Api, make_settings, make_video
    s = make_settings(tmp_path, redis_url=url)
    with TestClient(create_app(s)) as c:
        api = Api(c)
        admin = api.login("admin@example.org", "admin-password-1")
        assert c.get("/api/v1/health").json()["job_queue"] == "RedisJobs"
        u = api.user(admin)
        j = c.post("/api/v1/analysis/videos", files={"file": ("v.mp4", make_video(tmp_path / "z.mp4"), "video/mp4")},
                   headers=u).json()
        assert c.get(f"/api/v1/analysis/videos/{j['id']}", headers=u).json()["status"] == "queued"
        assert len(srv.lists[JOB_QUEUE]) == 1
        for k, v in {"DATABASE_URL": s.database_url, "STORAGE_DIR": str(s.storage_dir), "REDIS_URL": url,
                     "MODEL_REGISTRY_DIR": str(s.model_registry_dir), "JWT_SECRET": "t" * 40}.items():
            monkeypatch.setenv(k, v)
        from app import worker
        assert worker.run(max_jobs=1, block_seconds=1) == 1
        r = c.get(f"/api/v1/analysis/videos/{j['id']}", headers=u).json()
        assert r["status"] == "extractor_unavailable" and r["result"]["video"]["decodable"] is True
    srv.shutdown()
