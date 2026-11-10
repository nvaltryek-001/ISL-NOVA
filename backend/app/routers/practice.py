"""Practice Coach and Text-to-Sign: compare a learner's attempt with reference data.

Reference data (dataset/references/references_v1.npz) is derived from the INCLUDE
training split: a mean feature template per sign, one medoid recording's
landmarks for animation, and per-class distance calibration. The similarity
score is a learning aid, not an assessment of correct ISL: references come from
INCLUDE signers and the signs are not yet linguistically verified.
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
from pydantic import BaseModel, Field

from ..api import ApiError, Ctx, Router
from .ml import FrameIn

router = Router("practice")

PART_LABELS = {
    "left_hand_local": "left-hand shape", "right_hand_local": "right-hand shape", "left_angles": "left-hand finger bends",
    "right_angles": "right-hand finger bends", "wrists_body": "hand position relative to the body",
    "pose_body": "arm and shoulder posture", "two_hand": "distance between the hands", "presence": "which hands are used",
    "wrists_velocity": "movement speed and direction",
}
TIPS = {
    "left_hand_local": "Check the shape of your left hand against the reference.",
    "right_hand_local": "Check the shape of your right hand against the reference.",
    "left_angles": "Bend or straighten the fingers of your left hand as in the reference.",
    "right_angles": "Bend or straighten the fingers of your right hand as in the reference.",
    "wrists_body": "Place your hands at the same height and distance from the body as the reference.",
    "pose_body": "Keep your shoulders and arms in frame and match the arm position.",
    "two_hand": "Match how close together or far apart your hands are.",
    "presence": "Use the same hand(s) as the reference and keep both hands in view.",
    "wrists_velocity": "Match the movement: its direction, size and speed.",
}


class References:
    _lock = threading.Lock()
    _cache: dict[str, References] = {}

    def __init__(self, path: Path):
        z = np.load(path, allow_pickle=False)
        self.ids = [str(s) for s in z["sign_ids"]]
        self.index = {s: i for i, s in enumerate(self.ids)}
        self.templates = z["templates"].astype(np.float32)
        self.same = z["same_median"]
        self.other = z["other_median"]
        self.block_same = z["block_same_median"]
        self.block_names = [str(b) for b in z["block_names"]]
        self.lengths = z["lengths"]
        self.parts = {k: z[k] for k in ("left", "right", "pose")}
        self.masks = {k: z[f"{k}_mask"] for k in ("left", "right", "pose")}

    @classmethod
    def load(cls, directory: Path) -> References | None:
        p = Path(directory) / "references_v1.npz"
        if not p.exists():
            return None
        key = f"{p}:{p.stat().st_mtime}"
        with cls._lock:
            if key not in cls._cache:
                cls._cache = {key: cls(p)}
            return cls._cache[key]

    def frames(self, sign_id: str) -> list[dict]:
        i = self.index[sign_id]
        out = []
        for t in range(int(self.lengths[i])):
            out.append({k: (np.round(self.parts[k][i, t].astype(np.float32), 4).tolist() if self.masks[k][i, t] else None)
                        for k in ("left", "right", "pose")})
        return out


def refs_or_503(ctx: Ctx) -> References:
    r = References.load(ctx.app.settings.references_dir)
    if r is None:
        raise ApiError(503, "references_unavailable",
                       "sign reference data is not installed; run scripts/fetch_references.py (setup scripts do this)")
    return r


@router.get("/practice/status", summary="Whether practice reference data is installed", auth="optional")
def status(ctx: Ctx):
    r = References.load(ctx.app.settings.references_dir)
    return {"available": r is not None, "classes": len(r.ids) if r else 0,
            "source": "INCLUDE training split (Sridhar et al., ACM MM 2020), CC BY 4.0; landmarks only"}


@router.get("/practice/reference/{sign_id}", summary="Reference landmark sequence of a sign for animation", auth="optional")
def reference(ctx: Ctx):
    r = refs_or_503(ctx)
    sid = ctx.params["sign_id"]
    if sid not in r.index:
        raise ApiError(404, "not_found", f"no reference for {sid}")
    row = ctx.db.one("SELECT canonical_sign_name, verification_status FROM signs WHERE sign_id = ?", (sid,))
    return {"sign_id": sid, "label": row["canonical_sign_name"] if row else sid,
            "verification_status": row["verification_status"] if row else None, "fps": 12.5,
            "frames": r.frames(sid), "attribution": "INCLUDE (CC BY 4.0)"}


class ScoreIn(BaseModel):
    sign_id: str = Field(pattern=r"^ISL\d{3}$")
    frames: list[FrameIn] = Field(max_length=300)
    aspect: float = Field(default=4 / 3, gt=0.2, lt=5)


def score_attempt(r: References, sign_id: str, frames: list[dict], aspect: float) -> dict:
    from isl_nova_ml import contract as C
    from isl_nova_ml.features import extract_features

    fr = extract_features(frames, aspect)
    if fr.status != "ok":
        return {"state": "insufficient_input", "reasons": fr.reasons, "score": None, "parts": [], "tips": [
            "Keep both hands and your upper body in the camera view, with even lighting, and try again."]}
    i = r.index[sign_id]
    F = np.asarray(fr.features, np.float32)
    T = r.templates[i]
    d = float(np.sqrt(np.mean((F - T) ** 2)))
    same, other = float(r.same[i]), float(r.other[i])
    score = 100.0 * float(np.clip((other - d) / max(other - same, 1e-6), 0, 1))
    parts, off = [], 0
    for b, (name, size) in enumerate(C.BLOCKS):
        bd = float(np.sqrt(np.mean((F[:, off:off + size] - T[:, off:off + size]) ** 2)))
        ratio = bd / max(float(r.block_same[i, b]), 1e-6)
        parts.append({"part": name, "label": PART_LABELS.get(name, name), "ratio": round(ratio, 2),
                      "status": "good" if ratio <= 1.2 else "check" if ratio <= 1.8 else "different"})
        off += size
    worst = sorted([p for p in parts if p["status"] != "good"], key=lambda p: -p["ratio"])[:3]
    return {"state": "scored", "score": round(score, 1), "distance": round(d, 4),
            "typical_same_sign_distance": round(same, 4), "typical_other_sign_distance": round(other, 4),
            "parts": parts, "tips": [TIPS[p["part"]] for p in worst] or ["Close match to the reference. Keep practising for consistency."],
            "note": "Similarity to INCLUDE reference recordings; a learning aid, not a verified assessment."}


@router.post("/practice/score", summary="Score a practice attempt against the sign's reference", auth="optional",
             body=ScoreIn, rate="default")
def score(ctx: Ctx):
    r = refs_or_503(ctx)
    b: ScoreIn = ctx.body
    if b.sign_id not in r.index:
        raise ApiError(404, "not_found", f"no reference for {b.sign_id}")
    frames = [f.model_dump() for f in b.frames]
    out = score_attempt(r, b.sign_id, frames, b.aspect)
    p = ctx.app.models.predictor
    if p is not None and out["state"] == "scored":
        pr = p.predict(frames, b.aspect, 3)
        out["model"] = {"state": pr["state"], "top": pr["top"],
                        "matches_target": bool(pr["top"]) and pr["top"][0]["sign_id"] == b.sign_id}
    return out
