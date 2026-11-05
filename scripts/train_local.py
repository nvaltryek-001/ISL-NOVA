#!/usr/bin/env python3
"""Download the processed INCLUDE landmarks and train a model on your own computer.

    python scripts/train_local.py                       # LSTM (the released model's recipe)
    python scripts/train_local.py --model all           # LSTM, GRU, logistic regression, DTW
    python scripts/train_local.py --model pooled-logreg # fastest (about a minute)
    python scripts/train_local.py --promote             # make the new model the active one

Data: the 3,370 landmark sequences (176 MB) that the `INCLUDE data pipeline`
workflow extracted from the INCLUDE videos (CC BY 4.0). They are a GitHub
Actions artifact of run 41764539272, so downloading them needs the GitHub CLI
(`gh`, signed in with `gh auth login`). Alternatively download the artifact zip
from the run page in a browser, unzip it and pass --data <folder>.

Training uses the INCLUDE official train/val/test split, selects on
validation and evaluates the test split once, exactly as in CI. A new model is
registered but NOT promoted unless you pass --promote; the server must be
restarted to load a newly promoted model. Works on Windows, macOS and Linux.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "ml")]

REPO = "nvaltryek-001/ISL-NOVA"
DATA_RUN = "41764539272"
ARTIFACT = "include-landmarks-v1"
CONFIGS = {"lstm": "lstm_baseline.json", "gru": "gru.json", "pooled-logreg": "pooled-logreg.json", "dtw-1nn": "dtw-1nn.json"}


def fail(msg: str) -> None:
    print(f"ERROR  {msg}", file=sys.stderr)
    raise SystemExit(1)


def ensure_data(data: Path, run_id: str) -> Path:
    if (data / "manifest.json").exists():
        print(f"data: using {data}")
        return data
    gh = shutil.which("gh")
    if not gh:
        fail(f"no dataset at {data} and the GitHub CLI is not installed.\n"
             f"  Option 1: install it (https://cli.github.com/), run `gh auth login`, then rerun this script.\n"
             f"  Option 2: open https://github.com/{REPO}/actions/runs/{run_id}, download the '{ARTIFACT}' artifact,\n"
             f"            unzip it into {data} (so that {data / 'manifest.json'} exists) and rerun.")
    print(f"data: downloading artifact '{ARTIFACT}' from run {run_id} (~176 MB) ...")
    data.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([gh, "run", "download", run_id, "-R", REPO, "-n", ARTIFACT, "-D", str(data)])  # noqa: S603
    if r.returncode != 0 or not (data / "manifest.json").exists():
        fail("download failed. Check `gh auth status`; artifacts expire 90 days after the run (early February 2027).")
    return data


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="lstm", choices=[*CONFIGS, "all"])
    ap.add_argument("--data", type=Path, default=ROOT / "data" / ARTIFACT, help="folder containing manifest.json")
    ap.add_argument("--run-id", default=DATA_RUN, help="GitHub Actions run that produced the landmarks")
    ap.add_argument("--registry", type=Path, default=ROOT / "artifacts" / "models")
    ap.add_argument("--epochs", type=int, help="override the configured maximum epochs (early stopping still applies)")
    ap.add_argument("--seed", type=int, help="override the random seed (released model: 13)")
    ap.add_argument("--promote", action="store_true", help="promote the best new model (by validation macro-F1)")
    a = ap.parse_args(argv)

    from isl_nova_ml.registry import Registry
    from isl_nova_ml.train import run

    data = ensure_data(a.data, a.run_id)
    summary = json.loads((data / "manifest.json").read_text()).get("summary", {})
    if summary:
        print(f"data: {summary.get('usable_landmark_sequences')} sequences, {summary.get('classes_with_data')} classes, "
              f"split {summary.get('by_split')}")

    kinds = list(CONFIGS) if a.model == "all" else [a.model]
    results = []
    for kind in kinds:
        cfg = json.loads((ROOT / "ml" / "configs" / CONFIGS[kind]).read_text())
        if a.epochs:
            cfg["epochs"] = a.epochs
        if a.seed is not None:
            cfg["seed"] = a.seed
        print(f"\n==> training {kind} (max {cfg['epochs']} epochs, seed {cfg['seed']}) ...")
        t0 = time.time()
        res = run(cfg, data / "manifest.json", data, a.registry, ROOT / "dataset" / "vocabulary" / "signs_master.csv",
                  "include-official-v1")
        m = json.loads((Path(res["dir"]) / "metrics.json").read_text())
        results.append({"kind": kind, "model_id": res["model_id"], "minutes": round((time.time() - t0) / 60, 1),
                        "val_macro_f1": m["validation"]["macro_f1"], **{k: m["test"][k] for k in ("top1", "top5", "macro_f1", "weighted_f1")}})

    print("\n| model | id | val macro-F1 | test top-1 | test top-5 | test macro-F1 | minutes |")
    print("|---|---|---:|---:|---:|---:|---:|")
    for r in results:
        print(f"| {r['kind']} | {r['model_id']} | {r['val_macro_f1']:.3f} | {r['top1']:.3f} | {r['top5']:.3f} | {r['macro_f1']:.3f} | {r['minutes']} |")
    print("(released LSTM for comparison: val macro-F1 0.911, test top-1 0.917, top-5 0.983, macro-F1 0.917)")

    if a.promote:
        best = max(results, key=lambda r: r["val_macro_f1"])  # select on validation, never on test
        Registry(a.registry).promote(best["model_id"], actor="train_local")
        print(f"\npromoted {best['model_id']}. Restart the server to load it; roll back in AI Laboratory -> Registry.")
    else:
        print("\nNew models are registered but not active. Promote one in AI Laboratory -> Registry, "
              "or rerun with --promote.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
