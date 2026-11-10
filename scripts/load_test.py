#!/usr/bin/env python3
"""Load test for a running ISL NOVA server (standard library only).

    python scripts/load_test.py --base http://127.0.0.1:8000 --users 8 --seconds 60

Each simulated user loops over a realistic mix: health check (10 %), vocabulary
search (40 %), and a real held-out INCLUDE landmark sequence sent to
POST /api/v1/predict/sequence (50 %; the sample attached to the model release).
Prints throughput, latency percentiles per endpoint and the error rate, and
writes the same as JSON with --out. Rate limiting must be raised for the test
(RATE_LIMIT_PER_MINUTE) or every user is throttled to the per-IP budget.
"""

from __future__ import annotations

import argparse
import io
import json
import random
import statistics
import sys
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "ml")]

from isl_nova_ml.data import load_landmarks  # noqa: E402

REPO = "nvaltryek-001/ISL-NOVA"
QUERIES = ["hello", "water", "thank", "good", "morning", "red", "friend", "school", "मदद", "ನೀರು", "", "doctor"]


def _sample(tag: str, sample: Path | None) -> list[bytes]:
    if sample is None:
        sample = Path(tempfile.mkdtemp(prefix="isl-load-"))
        url = f"https://github.com/{REPO}/releases/download/{tag}/include_test_landmark_sample.tar.gz"
        with urllib.request.urlopen(url, timeout=120) as r:  # noqa: S310 - fixed https URL
            with tarfile.open(fileobj=io.BytesIO(r.read())) as tf:
                tf.extractall(sample, filter="data")
    man = json.loads((sample / "manifest.json").read_text())
    out = []
    for e in man["entries"]:
        frames, aspect = load_landmarks(sample / e["landmarks_path"])
        out.append(json.dumps({"frames": frames, "aspect": aspect}).encode())
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--users", type=int, default=8)
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--tag", default="model-bilstm_attn-20261110T162800Z-s7")
    ap.add_argument("--sample", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    base = a.base.rstrip("/")
    if not base.startswith(("http://127.0.0.1", "http://localhost", "https://")):
        raise SystemExit("refusing a non-https remote URL")
    bodies = _sample(a.tag, a.sample)
    lat = defaultdict(list)
    errors = defaultdict(int)
    statuses = defaultdict(int)
    lock = threading.Lock()
    stop_at = time.monotonic() + a.seconds

    def user(seed: int):
        rng = random.Random(seed)
        while time.monotonic() < stop_at:
            x = rng.random()
            if x < 0.1:
                name, req = "GET /health", urllib.request.Request(f"{base}/api/v1/health")  # noqa: S310
            elif x < 0.5:
                q = urllib.parse.quote(rng.choice(QUERIES))
                name, req = "GET /signs?q=", urllib.request.Request(f"{base}/api/v1/signs?size=24&q={q}")  # noqa: S310
            else:
                name = "POST /predict/sequence"
                req = urllib.request.Request(f"{base}/api/v1/predict/sequence", rng.choice(bodies),  # noqa: S310
                                             {"Content-Type": "application/json"})
            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 - base URL checked above
                    r.read()
                    code = r.status
            except urllib.error.HTTPError as e:
                code = e.code
            except OSError:
                code = 0
            dt = (time.perf_counter() - t0) * 1000
            with lock:
                lat[name].append(dt)
                statuses[code] += 1
                if code != 200:
                    errors[name] += 1

    threads = [threading.Thread(target=user, args=(i,)) for i in range(a.users)]
    t_start = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.monotonic() - t_start
    total = sum(len(v) for v in lat.values())

    def pct(v, p):
        return round(statistics.quantiles(v, n=100)[p - 1], 1) if len(v) >= 2 else (round(v[0], 1) if v else None)

    rep = {"base": base, "users": a.users, "seconds": round(elapsed, 1), "requests": total,
           "throughput_rps": round(total / elapsed, 1), "status_codes": dict(statuses),
           "error_rate": round(sum(errors.values()) / total, 4) if total else None,
           "endpoints": {k: {"n": len(v), "p50_ms": pct(v, 50), "p95_ms": pct(v, 95), "p99_ms": pct(v, 99),
                             "errors": errors.get(k, 0)} for k, v in sorted(lat.items())}}
    print(json.dumps(rep, indent=2))
    if a.out:
        a.out.write_text(json.dumps(rep, indent=2))
    return 0 if rep["error_rate"] is not None and rep["error_rate"] < 0.01 else 1


if __name__ == "__main__":
    raise SystemExit(main())
