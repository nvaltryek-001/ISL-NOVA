#!/usr/bin/env python3
"""Download the processed INCLUDE landmarks and train a model on your own computer.

    python scripts/train_local.py                       # LSTM (the released model's recipe)
    python scripts/train_local.py --model all           # LSTM, GRU, logistic regression, DTW
    python scripts/train_local.py --model pooled-logreg # fastest (about a minute)
    python scripts/train_local.py --promote             # make the new model the active one

Data: the 3,370 landmark sequences (~176 MB) that the `INCLUDE data pipeline`
workflow extracted from the INCLUDE videos (CC BY 4.0, attribution in the
archive). They are downloaded from the GitHub release
`dataset-include-landmarks-v1` (no sign-in, SHA-256 verified). Fallbacks: the
GitHub CLI (`gh run download`), or --data <folder> with the unzipped artifact.

Training uses the INCLUDE official train/val/test split, selects on
validation and evaluates the test split once, exactly as in CI. A new model is
registered but NOT promoted unless you pass --promote; the server must be
restarted to load a newly promoted model. Works on Windows, macOS and Linux.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "ml")]

REPO = "nvaltryek-001/ISL-NOVA"
DATA_RUN = "41764539272"
ARTIFACT = "include-landmarks-v1"
RELEASE = "dataset-include-landmarks-v1"
CONFIGS = {"lstm": "lstm_baseline.json", "lstm-fps": "lstm_fps_aug.json", "gru": "gru.json", "gru-fps": "gru_fps_aug.json",
           "bilstm-attn": "bilstm-attn_fps_aug.json", "transformer": "transformer_fps_aug.json", "tcn": "tcn_fps_aug.json",
           "pooled-logreg": "pooled-logreg.json", "dtw-1nn": "dtw-1nn.json"}
# need a dataset extracted with face points (scripts/include_local.py); not part of --model all on the 176 MB release
FACE_CONFIGS = {"lstm-face": "lstm_fps_aug_face.json", "bilstm-attn-face": "bilstm-attn_fps_aug_face.json",
                "transformer-face": "transformer_fps_aug_face.json", "tcn-face": "tcn_fps_aug_face.json"}
# need open-set (reserve gloss) entries in the manifest: train an extra "__other__" class
OTHER_CONFIGS = {"lstm-other": "lstm_fps_aug_other.json", "transformer-other": "transformer_fps_aug_other.json"}
ALL_CONFIGS = {**CONFIGS, **FACE_CONFIGS, **OTHER_CONFIGS}


def has_face(data: Path, manifest: dict) -> bool:
    import numpy as np

    e = (manifest.get("entries") or [{}])[0]
    if not e.get("landmarks_path"):
        return False
    with np.load(data / e["landmarks_path"]) as z:
        return "face_mask" in z


def fail(msg: str) -> None:
    print(f"ERROR  {msg}", file=sys.stderr)
    raise SystemExit(1)


def _https_get(url: str) -> bytes:
    if not url.startswith("https://"):
        fail(f"refusing non-https URL {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "isl-nova-train-local"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=600) as r:  # noqa: S310 - https only, checked above
        return r.read()


def from_release(data: Path) -> bool:
    """Download the published landmark archive (no sign-in needed) and verify its SHA-256."""
    base = f"https://github.com/{REPO}/releases/download/{RELEASE}"
    try:
        print(f"data: downloading {RELEASE} (~176 MB) from GitHub releases ...")
        want = _https_get(f"{base}/{ARTIFACT}.tar.gz.sha256").decode().split()[0]
        blob = _https_get(f"{base}/{ARTIFACT}.tar.gz")
    except urllib.error.URLError as e:
        print(f"data: release download not available ({e})")
        return False
    got = hashlib.sha256(blob).hexdigest()
    if got != want:
        fail(f"checksum mismatch for the dataset archive (expected {want}, got {got})")
    data.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(blob)) as tf:
        tf.extractall(data.parent, filter="data")  # archive root is include-landmarks-v1/
    if (data.parent / ARTIFACT) != data and (data.parent / ARTIFACT).exists():
        shutil.move(str(data.parent / ARTIFACT), str(data))
    print(f"data: SHA-256 verified, extracted to {data}")
    return (data / "manifest.json").exists()


def ensure_data(data: Path, run_id: str) -> Path:
    if (data / "manifest.json").exists():
        print(f"data: using {data}")
        return data
    if from_release(data):
        return data
    gh = shutil.which("gh")
    if not gh:
        fail(f"no dataset at {data}, the release download failed and the GitHub CLI is not installed.\n"
             f"  Open https://github.com/{REPO}/actions/runs/{run_id} while signed in, download the '{ARTIFACT}' artifact,\n"
             f"  unzip it into {data} (so that {data / 'manifest.json'} exists) and rerun.")
    print(f"data: downloading artifact '{ARTIFACT}' from run {run_id} with the GitHub CLI ...")
    data.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([gh, "run", "download", run_id, "-R", REPO, "-n", ARTIFACT, "-D", str(data)])  # noqa: S603
    if r.returncode != 0 or not (data / "manifest.json").exists():
        fail("download failed. Check `gh auth status`; artifacts expire 90 days after the run (early February 2027).")
    return data


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="lstm", choices=[*ALL_CONFIGS, "all", "all-face"],
                    help="all = the 9 hands+pose models; all-face = the 4 face models (needs a face dataset)")
    ap.add_argument("--data", type=Path, default=ROOT / "data" / ARTIFACT, help="folder containing manifest.json")
    ap.add_argument("--run-id", default=DATA_RUN, help="GitHub Actions run that produced the landmarks")
    ap.add_argument("--registry", type=Path, default=ROOT / "artifacts" / "models")
    ap.add_argument("--epochs", type=int, help="override the configured maximum epochs (early stopping still applies)")
    ap.add_argument("--seed", type=int, help="override the random seed (released model: 13)")
    ap.add_argument("--promote", action="store_true", help="promote the best new model (by validation macro-F1)")
    ap.add_argument("--download-only", action="store_true", help="only download and verify the dataset, do not train")
    a = ap.parse_args(argv)

    from isl_nova_ml.registry import Registry
    from isl_nova_ml.train import run

    data = ensure_data(a.data, a.run_id)
    manifest = json.loads((data / "manifest.json").read_text())
    summary = manifest.get("summary", {})
    if summary:
        print(f"data: {summary.get('usable_landmark_sequences')} sequences, {summary.get('classes_with_data')} classes, "
              f"split {summary.get('by_split')}")

    if a.download_only:
        print("data: ready (download only, no training)")
        return 0
    kinds = list(CONFIGS) if a.model == "all" else list(FACE_CONFIGS) if a.model == "all-face" else [a.model]
    if any(k in FACE_CONFIGS for k in kinds) and not has_face(data, manifest):
        fail(f"{data} has no face landmarks. Extract them first with: python scripts/include_local.py")
    if any(k in OTHER_CONFIGS for k in kinds) and not manifest.get("open_set_entries"):
        fail(f"{data} has no open-set (reserve gloss) entries. Extract them with: python scripts/include_local.py")
    results = []
    for kind in kinds:
        cfg = json.loads((ROOT / "ml" / "configs" / ALL_CONFIGS[kind]).read_text())
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
    print("(released models for comparison: v3 BiLSTM-attention val macro-F1 0.981, test top-1 0.951, top-5 0.994, "
          "macro-F1 0.941; v2 LSTM test top-1 0.920; v1 LSTM 0.917)")

    if a.promote:
        best = max(results, key=lambda r: r["val_macro_f1"])  # select on validation, never on test
        Registry(a.registry).promote(best["model_id"], actor="train_local")
        print(f"\npromoted {best['model_id']}.")
        if manifest.get("open_set_entries"):
            # fit the unknown-sign detector exactly as CI does (known validation + unknown part A2),
            # then evaluate it once on known test + unknown part B
            print("fitting the unknown-sign detector (calibrate-open-set) ...")
            out = a.registry / best["model_id"] / "open_set_report"
            r = subprocess.run([sys.executable, "-m", "isl_nova_ml.include_pipeline", "calibrate-open-set",  # noqa: S603
                                "--registry", str(a.registry), "--manifest", str(data / "manifest.json"),
                                "--data-root", str(data), "--out", str(out)], cwd=ROOT,
                               env={**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / 'ml'), str(ROOT / 'backend')])})
            if r.returncode == 0:
                rep = json.loads((out / "open_set_v3.json").read_text())["open_set_detector_rule"]
                print(f"unknown signs accepted (FAR) {rep['false_acceptance']:.1%}, known signs held back (FRR) "
                      f"{rep['false_rejection']:.1%}  (targets: FAR < 10 %, FRR <= 15 %)")
            else:
                print("calibration failed; the model still works with its max-probability rule")
        print("Restart the server to load it; roll back in AI Laboratory -> Registry.")
    else:
        print("\nNew models are registered but not active. Promote one in AI Laboratory -> Registry, "
              "or rerun with --promote.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
