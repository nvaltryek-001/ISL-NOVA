#!/usr/bin/env python3
"""Build per-sign reference data for the Practice Coach and the Text-to-Sign viewer.

    python dataset/scripts/build_references.py --data <include-landmarks-v1 folder>

Uses the INCLUDE **training** split only (CC BY 4.0, Sridhar et al. 2020):
  * template[c]  mean 32 x 204 feature-contract sequence of class c
  * medoid[c]    the training recording closest to the template (raw landmarks,
                 float16, for skeleton animation)
  * calibration  per class: distances of training recordings to their own
                 template (same) and to other templates (other), used to turn a
                 distance into a 0-100 similarity score
Writes dataset/references/references_v1.npz and references_v1.json (metadata).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "ml")]

from isl_nova_ml import contract as C  # noqa: E402
from isl_nova_ml.data import load_landmarks  # noqa: E402
from isl_nova_ml.features import extract_features  # noqa: E402


def dist(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.sqrt(np.mean((a - b) ** 2)))


def block_slices() -> list[tuple[str, slice]]:
    off, out = 0, []
    for name, size in C.BLOCKS:
        out.append((name, slice(off, off + size)))
        off += size
    return out


BLOCKS = block_slices()


def block_dists(a: np.ndarray, b: np.ndarray) -> list[float]:
    return [float(np.sqrt(np.mean((a[:, sl] - b[:, sl]) ** 2))) for _, sl in BLOCKS]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "dataset" / "references")
    a = ap.parse_args(argv)
    man = json.loads((a.data / "manifest.json").read_text())
    by: dict[str, list] = {}
    for e in man["entries"]:
        if e["split"] != "train" or e["quality"]["status"] != "ok":
            continue
        frames, aspect = load_landmarks(a.data / e["landmarks_path"])
        fr = extract_features(frames, aspect)
        if fr.status == "ok":
            by.setdefault(e["sign_id"], []).append((e, np.asarray(fr.features, np.float32), frames, aspect))
    ids = sorted(by)
    T = np.stack([np.mean([x[1] for x in by[s]], 0) for s in ids])
    same_med, other_med, medoid_frames, meta, block_med = [], [], [], [], []
    for i, s in enumerate(ids):
        ds = [dist(x[1], T[i]) for x in by[s]]
        others = [dist(x[1], T[j]) for x in by[s] for j in np.random.default_rng(i).choice(len(ids), 8, replace=False) if j != i]
        same_med.append(np.median(ds))
        block_med.append(np.median([block_dists(x[1], T[i]) for x in by[s]], 0))
        other_med.append(np.median(others))
        k = int(np.argmin(ds))
        e, _, frames, aspect = by[s][k]
        frames = frames[::2]  # 12.5 fps is enough for the skeleton animation
        medoid_frames.append(frames)
        meta.append({"sign_id": s, "gloss": e["gloss"], "recording_id": e["recording_id"], "aspect": aspect,
                     "frames": len(frames), "fps": 12.5, "train_recordings": len(by[s])})
    L = max(len(f) for f in medoid_frames)
    arrs = {k: np.zeros((len(ids), L, n, d), np.float16) for k, n, d in (("left", 21, 3), ("right", 21, 3), ("pose", 33, 4))}
    masks = {k: np.zeros((len(ids), L), bool) for k in arrs}
    for i, frames in enumerate(medoid_frames):
        for t, f in enumerate(frames):
            for k in arrs:
                if f.get(k) is not None:
                    arrs[k][i, t] = np.asarray(f[k], np.float16)
                    masks[k][i, t] = True
    a.out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(a.out / "references_v1.npz", sign_ids=np.array(ids), templates=T.astype(np.float16),
                        same_median=np.array(same_med, np.float32), block_same_median=np.array(block_med, np.float32),
                        block_names=np.array([n for n, _ in BLOCKS]), other_median=np.array(other_med, np.float32),
                        lengths=np.array([len(f) for f in medoid_frames]), **arrs,
                        **{f"{k}_mask": v for k, v in masks.items()})
    (a.out / "references_v1.json").write_text(json.dumps({
        "version": "references-v1", "feature_contract": C.CONTRACT_VERSION,
        "source": "INCLUDE training split (Sridhar et al., ACM MM 2020), CC BY 4.0; landmarks only, no video",
        "classes": len(ids), "signs": meta}, indent=1, ensure_ascii=False))
    print(f"references for {len(ids)} classes, max {L} frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
