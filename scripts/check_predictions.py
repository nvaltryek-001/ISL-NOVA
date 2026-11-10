#!/usr/bin/env python3
"""Send held-out INCLUDE test landmark sequences to a running ISL NOVA server.

    python scripts/check_predictions.py --base http://127.0.0.1:8000 \
        [--tag model-lstm-20261110T111537Z-s7] [--sample DIR] [--min-correct 0.75]

Downloads the 24-sequence held-out test sample attached to the model release
(unless --sample points at an extracted copy), posts each sequence to
POST /api/v1/predict/sequence and prints per-sample results and top-1.
Works the same on Windows, macOS and Linux. Exit code 1 if top-1 is below
--min-correct.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "ml")]

from isl_nova_ml.data import load_landmarks  # noqa: E402

REPO = "nvaltryek-001/ISL-NOVA"


def _get(url: str) -> bytes:
    if not url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
        raise SystemExit(f"refusing non-https URL: {url}")
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "isl-nova-check"}), timeout=120) as r:  # noqa: S310
        return r.read()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--tag", default="model-lstm-20261110T111537Z-s7")
    ap.add_argument("--sample", type=Path, help="directory with an extracted include_test_landmark_sample")
    ap.add_argument("--min-correct", type=float, default=0.75)
    a = ap.parse_args(argv)

    sample = a.sample
    if sample is None:
        sample = Path(tempfile.mkdtemp(prefix="isl-sample-"))
        blob = _get(f"https://github.com/{REPO}/releases/download/{a.tag}/include_test_landmark_sample.tar.gz")
        with tarfile.open(fileobj=io.BytesIO(blob)) as tf:
            tf.extractall(sample, filter="data")
    man = json.loads((sample / "manifest.json").read_text())
    base = a.base.rstrip("/")
    info = json.loads(_get(f"{base}/api/v1/model/info"))
    print(f"server model: {info.get('model_id')} available={info.get('available')} classes={info.get('n_classes')}")
    ok = 0
    for e in man["entries"]:
        frames, aspect = load_landmarks(sample / e["landmarks_path"])
        req = urllib.request.Request(f"{base}/api/v1/predict/sequence", json.dumps({"frames": frames, "aspect": aspect}).encode(),  # noqa: S310
                                     {"Content-Type": "application/json"})
        if not req.full_url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
            raise SystemExit("refusing non-https URL")
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
            out = json.loads(r.read())
        top = out["top"][0]["sign_id"] if out.get("top") else None
        ok += top == e["sign_id"]
        print(f"  {e['sign_id']:<7} predicted {top or '-':<7} {out['state']:<12} {'OK' if top == e['sign_id'] else 'MISS'}")
    n = len(man["entries"])
    print(f"held-out sample top-1: {ok}/{n}")
    return 0 if n and ok >= a.min_correct * n else 1


if __name__ == "__main__":
    raise SystemExit(main())
