#!/usr/bin/env python3
"""Install a trained model published as a GitHub pre-release into a model registry.

    PYTHONPATH=backend:ml python scripts/fetch_model.py --tag model-<model_id> \
        --registry artifacts/models [--promote]

Downloads <model_id>.tar.gz and its .sha256 from the release, verifies the
checksum, unpacks it into the registry (path-safe), verifies the weights hash,
registers it, optionally promotes it, and runs a load check through the same
Predictor the API uses.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "ml")]

from isl_nova_ml.inference import Predictor  # noqa: E402
from isl_nova_ml.registry import Registry, verify_integrity  # noqa: E402

REPO = "nvaltryek-001/ISL-NOVA"


def get(url: str) -> bytes:
    if not url.startswith("https://"):
        raise ValueError("https only")
    req = urllib.request.Request(url, headers={"User-Agent": "isl-nova-fetch-model"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=300) as r:  # noqa: S310
        return r.read()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", required=True, help="release tag, e.g. model-lstm-20261104T...")
    ap.add_argument("--registry", type=Path, default=ROOT / "artifacts" / "models")
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--promote", action="store_true")
    a = ap.parse_args(argv)
    model_id = a.tag.removeprefix("model-")
    base = f"https://github.com/{a.repo}/releases/download/{a.tag}/{model_id}.tar.gz"
    blob = get(base)
    want = get(base + ".sha256").decode().split()[0]
    got = hashlib.sha256(blob).hexdigest()
    if got != want:
        raise SystemExit(f"checksum mismatch: {got} != {want}")
    a.registry.mkdir(parents=True, exist_ok=True)
    root = a.registry.resolve()
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        for m in tf.getmembers():
            target = (root / m.name).resolve()
            if root not in target.parents or not (m.isfile() or m.isdir()):
                raise SystemExit(f"unsafe archive member {m.name!r}")
        tf.extractall(root, filter="data")
    d = root / model_id
    verify_integrity(d)
    reg = Registry(root)
    if not any(m["model_id"] == model_id for m in reg.read()["models"]):
        reg.register(d)
    if a.promote:
        reg.promote(model_id, actor="scripts/fetch_model.py")
    p = Predictor(d)
    print(json.dumps({"installed": model_id, "kind": p.info["kind"], "classes": len(p.classes),
                      "synthetic": p.synthetic, "promoted": a.promote, "sha256": got}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
