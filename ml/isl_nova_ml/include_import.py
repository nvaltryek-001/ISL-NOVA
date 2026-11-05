"""Import the INCLUDE dataset (CC BY 4.0) into an ISL NOVA training manifest.

Prerequisites (performed by the user; the dataset is 56.8 GB):
  1. Download the category zip files from https://zenodo.org/records/4010759
     and extract them so that paths look like ``<root>/Greetings/48. Hello/MVI_xxxx.MOV``
     (the official split lists use ``Days_and_Time``-style folder names; both
     spaces and underscores are accepted).
  2. Download MediaPipe ``hand_landmarker.task`` and ``pose_landmarker_lite.task``.

    python -m isl_nova_ml.include_import --include-root /data/INCLUDE \
        --out data/processed/include --hand-model models/hand_landmarker.task \
        --pose-model models/pose_landmarker_lite.task

Only classes that occupy one of the 200 ISL NOVA slots are imported. The
official train/val/test lists are kept. INCLUDE does not publish signer ids, so
entries carry ``signer_id="unknown:include"`` and signer independence of the
official split cannot be verified (reported in every model's lineage).
Imported entries are marked ``approved: false`` until a reviewer approves the
batch (``--approve`` records that decision explicitly).
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .data import save_landmarks
from .features import extract_features

REPO = Path(__file__).resolve().parents[2]
SPLITS = REPO / "dataset" / "sources" / "include"


def _norm(folder: str) -> str:
    return "".join(ch for ch in folder if ch.isalpha()).lower()


def gloss_to_sign_id(vocab: Path) -> dict[str, str]:
    with vocab.open(newline="", encoding="utf-8") as fh:
        return {r["source_gloss"]: r["sign_id"] for r in csv.DictReader(fh)}


def plan(include_root: Path, vocab: Path) -> list[dict]:
    g2s = gloss_to_sign_id(vocab)
    items = []
    for split in ("train", "val", "test"):
        for line in (SPLITS / f"include_{split}.txt").read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            cat, folder, fname = line.split("/", 2)
            sid = g2s.get(_norm(folder))
            if sid is None:
                continue
            cands = [include_root / cat / folder / fname, include_root / cat.replace("_", " ") / folder / fname]
            src = next((c for c in cands if c.exists()), cands[0])
            rid = f"include:{_norm(folder)}:{Path(fname).stem}"
            items.append({"recording_id": rid, "sign_id": sid, "split": split, "video": src})
    return items


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--include-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--vocab", type=Path, default=REPO / "dataset" / "vocabulary" / "signs_master.csv")
    ap.add_argument("--hand-model", type=Path)
    ap.add_argument("--pose-model", type=Path)
    ap.add_argument("--approve", action="store_true", help="mark imported entries as reviewer-approved")
    ap.add_argument("--limit", type=int, default=0, help="import at most N videos (for a dry run)")
    a = ap.parse_args(argv)

    from .extract import LandmarkExtractor

    items = plan(a.include_root, a.vocab)
    if a.limit:
        items = items[: a.limit]
    missing = [i for i in items if not i["video"].exists()]
    print(f"planned={len(items)} missing_videos={len(missing)}")
    ex = LandmarkExtractor(a.hand_model, a.pose_model)
    entries, failures = [], []
    try:
        for n, it in enumerate(items, 1):
            if not it["video"].exists():
                failures.append({"recording_id": it["recording_id"], "reason": "video file not found"})
                continue
            try:
                frames, aspect, meta = ex.video(it["video"])
            except Exception as exc:  # noqa: BLE001 - record and continue
                failures.append({"recording_id": it["recording_id"], "reason": str(exc)})
                continue
            rel = f"landmarks/{it['recording_id'].replace(':', '_')}.npz"
            sha = save_landmarks(a.out / rel, frames, aspect)
            q = extract_features(frames, aspect)
            entries.append({
                "recording_id": it["recording_id"], "sign_id": it["sign_id"], "split": it["split"],
                "signer_id": "unknown:include", "session_id": "unknown:include", "landmarks_path": rel,
                "sha256": sha, "source": "include", "license": "CC BY 4.0", "approved": bool(a.approve),
                "quality": {"status": q.status, "hand_frame_ratio": q.hand_frame_ratio, **meta},
            })
            if n % 50 == 0:
                print(f"  {n}/{len(items)}")
    finally:
        ex.close()
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "manifest.json").write_text(json.dumps({
        "source": "INCLUDE (doi:10.1145/3394171.3413528, CC BY 4.0)",
        "entries": entries, "failures": failures}, indent=1))
    print(f"imported={len(entries)} failed={len(failures)} -> {a.out / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
