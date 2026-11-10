#!/usr/bin/env python3
"""Engineering benchmark: feature extraction, model inference and API latency.

    PYTHONPATH=backend:ml python scripts/benchmark.py

Uses SYNTHETIC landmark sequences, so it measures speed only. It says nothing
about recognition accuracy.
"""

from __future__ import annotations

import json
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "ml")]

import numpy as np  # noqa: E402
from isl_nova_ml import contract as C  # noqa: E402
from isl_nova_ml.features import extract_features  # noqa: E402
from isl_nova_ml.models import GRUClassifier, LSTMClassifier, PooledLogReg  # noqa: E402
from isl_nova_ml.synthetic import make_sequence  # noqa: E402


def timeit(fn, n):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1000)
    ts.sort()
    return {"median_ms": round(statistics.median(ts), 3), "p95_ms": round(ts[int(0.95 * (len(ts) - 1))], 3), "n": n}


def main() -> None:
    rng = np.random.default_rng(0)
    frames = make_sequence(3, rng, 45)
    feats = extract_features(frames, 4 / 3).features[None].astype(np.float64)
    res = {"machine": {"python": platform.python_version(), "cpu_count": os.cpu_count(), "platform": platform.platform()},
           "contract": C.CONTRACT_NAME, "input": "45-frame synthetic two-hand sequence"}
    res["feature_extraction"] = timeit(lambda: extract_features(frames, 4 / 3), 200)
    X = rng.normal(size=(64, C.SEQUENCE_LENGTH, C.FEATURE_DIM))
    for name, m in (("lstm_h128_200cls", LSTMClassifier(C.FEATURE_DIM, 200, 128)),
                    ("gru_h128_200cls", GRUClassifier(C.FEATURE_DIM, 200, 128))):
        m.norm.fit(X)
        res[f"inference_{name}"] = timeit(lambda m=m: m.predict_proba(feats), 100)
        res[f"params_{name}"] = int(sum(v.size for v in m.p.values()))
    lr = PooledLogReg(C.FEATURE_DIM, 200).fit(X.repeat(4, 0), np.arange(256) % 200)
    res["inference_pooled_logreg_200cls"] = timeit(lambda: lr.predict_proba(feats), 200)

    from app.config import Settings
    from app.main import create_app
    from starlette.testclient import TestClient

    with tempfile.TemporaryDirectory() as d:
        s = Settings.from_env(database_url=f"sqlite:///{d}/b.db", storage_dir=Path(d) / "o",
                              model_registry_dir=Path(d) / "m", pbkdf2_iterations=1000, jwt_secret="b" * 40,
                              rate_limit_per_minute=10**6, frontend_dist=Path(d) / "none")
        with TestClient(create_app(s)) as c:
            body = {"frames": frames, "aspect": 4 / 3}
            res["api_get_signs_search"] = timeit(lambda: c.get("/api/v1/signs?q=good&size=24"), 100)
            res["api_get_dataset_stats"] = timeit(lambda: c.get("/api/v1/dataset/stats"), 100)
            res["api_predict_no_model"] = timeit(lambda: c.post("/api/v1/predict/sequence", json=body), 100)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
