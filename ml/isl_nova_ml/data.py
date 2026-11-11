"""Training manifests, landmark files, splits and leakage checks."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .features import extract_features

REQUIRED = ("recording_id", "sign_id", "signer_id", "session_id", "landmarks_path", "source")
TRAINING_CONSENT = "model_training"
LICENSES_ALLOWING_TRAINING = {"CC BY 4.0", "CC-BY-4.0", "project-consent", "synthetic-test-only"}


class ManifestError(ValueError):
    pass


def load_manifest(path: Path) -> list[dict]:
    data = json.loads(Path(path).read_text())
    entries = data["entries"] if isinstance(data, dict) else data
    errors = []
    seen = set()
    for i, e in enumerate(entries):
        miss = [k for k in REQUIRED if not e.get(k)]
        if miss:
            errors.append(f"entry {i}: missing {miss}")
        rid = e.get("recording_id")
        if rid in seen:
            errors.append(f"entry {i}: duplicate recording_id {rid}")
        seen.add(rid)
        if e.get("split") not in (None, "train", "val", "test"):
            errors.append(f"entry {i}: invalid split {e.get('split')!r}")
    if errors:
        raise ManifestError("; ".join(errors[:20]))
    return entries


def training_eligible(e: dict) -> tuple[bool, str]:
    if not e.get("approved", False):
        return False, "not approved by reviewer"
    lic = e.get("license", "")
    if lic not in LICENSES_ALLOWING_TRAINING:
        return False, f"license {lic!r} not cleared for training"
    if e.get("source") == "local" and TRAINING_CONSENT not in (e.get("consent_scope") or []):
        return False, "signer consent does not include model_training"
    return True, "ok"


# --- landmark files ----------------------------------------------------------

def save_landmarks(path: Path, frames: list[dict], aspect: float) -> str:
    n = len(frames)
    arrs = {"aspect": np.array(aspect, dtype=np.float64)}
    keys = [("left", 21, 3), ("right", 21, 3), ("pose", 33, 4)]
    if any(f.get("face") is not None for f in frames):  # non-manual landmarks (contract 2.0.0)
        keys.append(("face", 22, 3))
    for key, pts, dims in keys:
        a = np.zeros((n, pts, dims), dtype=np.float32)
        m = np.zeros(n, dtype=bool)
        for i, f in enumerate(frames):
            v = f.get(key)
            if v is not None:
                v = np.asarray(v, dtype=np.float32)
                a[i, :, : v.shape[1]] = v[:pts, :dims]
                m[i] = True
        arrs[key], arrs[f"{key}_mask"] = a, m
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrs)
    return sha256_file(path)


def load_landmarks(path: Path) -> tuple[list[dict], float]:
    with np.load(path, allow_pickle=False) as z:
        aspect = float(z["aspect"])
        n = len(z["left_mask"])
        frames = []
        for i in range(n):
            keys = ("left", "right", "pose", "face") if "face_mask" in z else ("left", "right", "pose")
            frames.append({k: (z[k][i].tolist() if z[f"{k}_mask"][i] else None) for k in keys})
    return frames, aspect


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --- splits -------------------------------------------------------------------

def assign_splits(entries: list[dict], seed: int = 13, val_frac: float = 0.15, test_frac: float = 0.15) -> list[dict]:
    """Signer-independent split. Entries that already carry a split keep it.

    Signers are shuffled deterministically and allocated to test/val/train so
    that no signer appears in more than one partition.
    """
    out = [dict(e) for e in entries]
    free = [e for e in out if not e.get("split")]
    signers = sorted({e["signer_id"] for e in free})
    rng = np.random.default_rng(seed)
    rng.shuffle(signers)
    n = len(signers)
    n_test = max(1, round(n * test_frac)) if n >= 3 else 0
    n_val = max(1, round(n * val_frac)) if n >= 3 else 0
    part = {}
    for i, s in enumerate(signers):
        part[s] = "test" if i < n_test else "val" if i < n_test + n_val else "train"
    for e in free:
        e["split"] = part[e["signer_id"]]
    return out


def leakage_report(entries: list[dict]) -> dict:
    by = defaultdict(lambda: defaultdict(set))
    for e in entries:
        sp = e.get("split")
        # ids prefixed "unknown" mean the source does not identify signers or
        # sessions; they cannot be checked and are counted, not compared.
        if not str(e["signer_id"]).startswith("unknown"):
            by["signer_id"][e["signer_id"]].add(sp)
        if not str(e["session_id"]).startswith("unknown"):
            by["session_id"][e["session_id"]].add(sp)
        if e.get("sha256"):
            by["sha256"][e["sha256"]].add(sp)
    report = {}
    for key, groups in by.items():
        report[key] = sorted(k for k, sps in groups.items() if len(sps) > 1)
    dup_ids = [k for k, c in Counter(e["recording_id"] for e in entries).items() if c > 1]
    report["duplicate_recording_ids"] = dup_ids
    # INCLUDE ships its own split without signer ids; signer leakage there is
    # unknown rather than absent, so it is reported separately.
    report["signer_ids_unknown"] = sum(1 for e in entries if str(e["signer_id"]).startswith("unknown"))
    report["has_leakage"] = any(report.get(k) for k in ("signer_id", "session_id", "sha256", "duplicate_recording_ids"))
    return report


@dataclass
class Tensors:
    X: np.ndarray
    y: np.ndarray
    ids: list[str]
    skipped: list[tuple[str, str]]


def build_tensors(entries: list[dict], root: Path, class_index: dict[str, int],
                  raw_aug_copies: int = 0, seed: int = 0, version: str = "1.0.0") -> Tensors:
    """Feature tensors for a split. With raw_aug_copies > 0 (training only), each
    sequence also contributes that many raw-level augmented variants (see
    augment.raw_variant); their ids carry a '#aug<k>' suffix."""
    X, y, ids, skipped = [], [], [], []
    rng = np.random.default_rng(seed)
    for e in entries:
        if e["sign_id"] not in class_index:
            skipped.append((e["recording_id"], "class not in model vocabulary"))
            continue
        frames, aspect = load_landmarks(root / e["landmarks_path"])
        fr = extract_features(frames, aspect, version)
        if fr.status != "ok":
            skipped.append((e["recording_id"], "; ".join(fr.reasons)))
            continue
        X.append(fr.features)
        y.append(class_index[e["sign_id"]])
        ids.append(e["recording_id"])
        if raw_aug_copies:
            from .augment import raw_variant
            for k in range(raw_aug_copies):
                fa = extract_features(raw_variant(frames, rng), aspect, version)
                if fa.status == "ok":
                    X.append(fa.features)
                    y.append(class_index[e["sign_id"]])
                    ids.append(f"{e['recording_id']}#aug{k}")
    if not X:
        from .contract import SEQUENCE_LENGTH, dim_for
        return Tensors(np.zeros((0, SEQUENCE_LENGTH, dim_for(version)), np.float32), np.zeros(0, int), [], skipped)
    return Tensors(np.stack(X), np.array(y), ids, skipped)
