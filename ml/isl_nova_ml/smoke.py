"""End-to-end SYNTHETIC smoke test of the training pipeline.

    python -m isl_nova_ml.smoke --out /tmp/isl-nova-smoke

It writes procedurally generated (non-ISL) landmark sequences, trains every
implemented model kind on them, and prints the resulting metrics. The numbers
only demonstrate that the code paths execute; they say nothing about ISL
recognition and must never be reported as project results.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .synthetic import write_synthetic_dataset
from .train import run


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--models", default="pooled_logreg,lstm,gru,dtw_1nn")
    ap.add_argument("--epochs", type=int, default=12)
    a = ap.parse_args(argv)
    data = a.out / "data"
    write_synthetic_dataset(data)
    results = {}
    for kind in a.models.split(","):
        cfg = {"experiment_name": f"synthetic-smoke-{kind}", "model": kind, "epochs": a.epochs,
               "hidden": 24, "batch_size": 16, "patience": 5}
        r = run(cfg, data / "manifest.json", data, a.out / "registry", None, "synthetic-smoke")
        results[kind] = {"model_id": r["model_id"], **r["summary"], "open_set": r["open_set"]}
    print("SYNTHETIC SMOKE TEST - NOT ISL RESULTS")
    print(json.dumps(results, indent=2, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
