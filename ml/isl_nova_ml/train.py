"""Training / evaluation pipeline.

    python -m isl_nova_ml.train --config ml/configs/lstm_baseline.json \
        --manifest data/processed/include/manifest.json --data-root data/processed/include \
        --registry artifacts/models --vocab dataset/vocabulary/signs_master.csv

Guarantees
* Only training-eligible entries (approved, licensed, consented) are used.
* Splits are signer-independent unless the source ships an official split.
* Training aborts on split leakage (shared signer/session/hash across splits).
* Model selection, early stopping, temperature and rejection threshold use the
  validation split only; the test split is evaluated exactly once at the end.
* Synthetic data cannot be mixed with real data and is flagged in every artefact.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from . import contract as C
from .augment import augment_batch
from .data import assign_splits, build_tensors, leakage_report, load_manifest, sha256_file, training_eligible
from .metrics import choose_threshold, classification_report, open_set_report
from .models import REGISTRY, fit_temperature, save_model, softmax
from .registry import Registry

DEFAULTS = {
    "experiment_name": "unnamed", "model": "lstm", "hidden": 64, "epochs": 40, "batch_size": 32,
    "lr": 3e-3, "weight_decay": 1e-4, "patience": 8, "lr_decay": 0.5, "lr_patience": 3,
    "augment": True, "seed": 13, "min_train_samples": 2, "class_weighting": "inverse_sqrt",
    "tau_keep": 0.95, "margin": 0.10, "dtw_window": 6, "logreg_C": 1.0,
}


class TrainingError(RuntimeError):
    pass


def _labels(vocab: Path | None) -> dict[str, str]:
    if vocab is None or not vocab.exists():
        return {}
    with vocab.open(newline="", encoding="utf-8") as fh:
        return {r["sign_id"]: r["canonical_sign_name"] for r in csv.DictReader(fh)}


def run(config: dict, manifest_path: Path, data_root: Path, registry_root: Path,
        vocab: Path | None = None, dataset_version: str = "unversioned", log=print) -> dict:
    cfg = {**DEFAULTS, **config}
    rng = np.random.default_rng(cfg["seed"])
    entries = load_manifest(manifest_path)
    raw = json.loads(manifest_path.read_text())
    sources = {e["source"] for e in entries}
    synthetic = "synthetic" in sources
    if synthetic and len(sources) > 1:
        raise TrainingError("synthetic data must never be mixed with real recordings")

    eligible, excluded = [], Counter()
    for e in entries:
        ok, why = training_eligible(e)
        (eligible.append(e) if ok else excluded.update([why]))
    if not eligible:
        raise TrainingError("no training-eligible entries (approval/licence/consent)")
    split_entries = assign_splits(eligible, seed=cfg["seed"])
    leak = leakage_report(split_entries)
    if leak["has_leakage"]:
        raise TrainingError(f"split leakage detected: {json.dumps({k: v for k, v in leak.items() if v})}")

    tr = [e for e in split_entries if e["split"] == "train"]
    va = [e for e in split_entries if e["split"] == "val"]
    te = [e for e in split_entries if e["split"] == "test"]
    counts = Counter(e["sign_id"] for e in tr)
    class_ids = sorted(c for c, n in counts.items() if n >= cfg["min_train_samples"])
    if len(class_ids) < 2:
        raise TrainingError("fewer than 2 classes meet min_train_samples")
    cidx = {c: i for i, c in enumerate(class_ids)}
    labels = _labels(vocab)

    log(f"[data] eligible={len(eligible)} excluded={dict(excluded)} classes={len(class_ids)} "
        f"train/val/test={len(tr)}/{len(va)}/{len(te)} synthetic={synthetic}")
    Ttr, Tva, Tte = (build_tensors(s, data_root, cidx) for s in (tr, va, te))
    if len(Tva.y) == 0 or len(Tte.y) == 0:
        raise TrainingError("validation and test splits must both contain usable samples")

    freq = np.bincount(Ttr.y, minlength=len(class_ids)).astype(float)
    if cfg["class_weighting"] == "inverse_sqrt":
        cw = 1.0 / np.sqrt(np.maximum(freq, 1))
    elif cfg["class_weighting"] == "inverse":
        cw = 1.0 / np.maximum(freq, 1)
    else:
        cw = np.ones_like(freq)
    cw = cw / cw[Ttr.y].mean()
    w = cw[Ttr.y]

    kind = cfg["model"]
    cls = REGISTRY[kind]
    D, Cn = C.FEATURE_DIM, len(class_ids)
    history = []
    t_start = time.perf_counter()
    if kind in ("lstm", "gru"):
        model = cls(D, Cn, cfg["hidden"], cfg["seed"])
        model.norm.fit(Ttr.X)
        opt = model.make_optimizer(cfg["lr"], cfg["weight_decay"])
        best, best_state, bad, lr_bad = -1.0, None, 0, 0
        for ep in range(1, cfg["epochs"] + 1):
            loss = model.train_epoch(Ttr.X, Ttr.y, w, opt, cfg["batch_size"], rng,
                                     augment_batch if cfg["augment"] else None)
            Pv = model.predict_proba(Tva.X)
            rep = classification_report(Pv, Tva.y, Cn)
            history.append({"epoch": ep, "train_loss": round(loss, 5), "val_top1": rep["top1"],
                            "val_macro_f1": rep["macro_f1"], "lr": opt.lr})
            log(f"[epoch {ep:03d}] loss={loss:.4f} val_top1={rep['top1']:.3f} val_macroF1={rep['macro_f1']:.3f}")
            if rep["macro_f1"] > best + 1e-6:
                best, bad, lr_bad = rep["macro_f1"], 0, 0
                best_state = {k: v.copy() for k, v in model.p.items()}
            else:
                bad += 1
                lr_bad += 1
                if lr_bad >= cfg["lr_patience"]:
                    opt.lr *= cfg["lr_decay"]
                    lr_bad = 0
                if bad >= cfg["patience"]:
                    log(f"[early-stop] epoch {ep}")
                    break
        model.p = best_state
    elif kind == "pooled_logreg":
        model = cls(D, Cn, cfg["logreg_C"], cfg["seed"]).fit(Ttr.X, Ttr.y, w)
    elif kind == "dtw_1nn":
        model = cls(D, Cn, cfg["dtw_window"], cfg["seed"]).fit(Ttr.X, Ttr.y)
        raw_v = model.logits(Tva.X)
        model.scale = float(np.median(-raw_v.max(1))) or 1.0
    else:
        raise TrainingError(f"unknown model {kind}")
    train_seconds = time.perf_counter() - t_start

    # calibration + threshold on validation only
    model.temperature = 1.0
    model.temperature = fit_temperature(model.logits(Tva.X), Tva.y)
    Pv = model.predict_proba(Tva.X)
    tau = choose_threshold(Pv, Tva.y, cfg["tau_keep"])

    # single final evaluation on test
    t0 = time.perf_counter()
    Pt = model.predict_proba(Tte.X)
    latency_ms = (time.perf_counter() - t0) * 1000 / max(len(Tte.y), 1)
    test = classification_report(Pt, Tte.y, Cn)
    val = classification_report(Pv, Tva.y, Cn)

    open_set = None
    if raw.get("open_set_entries"):
        unk = [e for e in raw["open_set_entries"] if training_eligible(e)[0]]
        from .data import load_landmarks
        from .features import extract_features
        Xu = [extract_features(*load_landmarks(data_root / e["landmarks_path"])).features for e in unk]
        Pu = model.predict_proba(np.stack(Xu)) if Xu else np.zeros((0, Cn))
        open_set = open_set_report(Pt, Pu, tau)

    by_signer = {}
    test_sid = {e["recording_id"]: e["signer_id"] for e in te}
    for s in sorted({test_sid[r] for r in Tte.ids}):
        m = np.array([test_sid[r] == s for r in Tte.ids])
        by_signer[s] = {"n": int(m.sum()), "top1": float((Pt[m].argmax(1) == Tte.y[m]).mean())}

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    model_id = f"{'syn-' if synthetic else ''}{kind}-{stamp}-s{cfg['seed']}"
    out = Path(registry_root) / model_id
    save_model(model, out)
    classes = [{"index": i, "sign_id": c, "label": labels.get(c, c)} for i, c in enumerate(class_ids)]
    summary = {"val_top1": val["top1"], "val_macro_f1": val["macro_f1"], "test_top1": test["top1"],
               "test_top5": test["top5"], "test_macro_f1": test["macro_f1"],
               "test_weighted_f1": test["weighted_f1"], "test_ece": test["ece"]}
    info = {
        "model_id": model_id, "kind": kind, "created_utc": stamp, "synthetic": synthetic,
        "warning": "SYNTHETIC SMOKE-TEST MODEL - NOT ISL - DO NOT REPORT" if synthetic else None,
        "contract": {"name": C.CONTRACT_NAME, "version": C.CONTRACT_VERSION, "feature_dim": C.FEATURE_DIM,
                     "sequence_length": C.SEQUENCE_LENGTH},
        "classes": classes,
        "thresholds": {"tau": tau, "margin": cfg["margin"], "temperature": model.temperature},
        "config": cfg,
        "lineage": {"dataset_version": dataset_version, "manifest_sha256": sha256_file(manifest_path),
                    "split_policy": "official/source split where provided, else signer-independent",
                    "split_counts": {"train": len(Ttr.y), "val": len(Tva.y), "test": len(Tte.y)},
                    "train_recording_ids": Ttr.ids, "val_recording_ids": Tva.ids, "test_recording_ids": Tte.ids,
                    "skipped": Ttr.skipped + Tva.skipped + Tte.skipped, "excluded": dict(excluded),
                    "leakage": leak},
        "metrics_summary": summary,
        "weights_sha256": sha256_file(out / "weights.npz"),
        "model_size_bytes": (out / "weights.npz").stat().st_size,
        "train_seconds": round(train_seconds, 2),
    }
    (out / "model.json").write_text(json.dumps(info, indent=2))
    metrics = {"model_id": model_id, "synthetic": synthetic, "validation": val, "test": test,
               "open_set": open_set, "per_signer_test": by_signer,
               "latency_ms_per_sample_batch": round(latency_ms, 3),
               "model_size_bytes": info["model_size_bytes"]}
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    with (out / "training_log.jsonl").open("w") as fh:
        for h in history:
            fh.write(json.dumps(h) + "\n")
    Registry(registry_root).register(out)
    log(f"[done] {model_id} test_top1={test['top1']:.3f} macroF1={test['macro_f1']:.3f} synthetic={synthetic}")
    return {"model_id": model_id, "dir": str(out), "summary": summary, "synthetic": synthetic,
            "open_set": open_set, "softmax_check": float(softmax(np.zeros((1, 2))).sum())}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--registry", type=Path, default=Path("artifacts/models"))
    ap.add_argument("--vocab", type=Path, default=Path("dataset/vocabulary/signs_master.csv"))
    ap.add_argument("--dataset-version", default="unversioned")
    a = ap.parse_args(argv)
    res = run(json.loads(a.config.read_text()), a.manifest, a.data_root, a.registry, a.vocab, a.dataset_version)
    print(json.dumps({k: res[k] for k in ("model_id", "summary", "synthetic")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
