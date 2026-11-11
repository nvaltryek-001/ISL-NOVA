"""Landmark sequence -> model input, implementing contract isl-nova-fc-1.0.0.

Raw frame format (one dict per video frame, MediaPipe image coordinates):

    {"left": [[x, y, z] * 21] | None,
     "right": [[x, y, z] * 21] | None,
     "pose": [[x, y, z, (visibility)] * 33] | None}

``left``/``right`` follow MediaPipe's handedness label on the *unmirrored*
frame. x and y are in [0, 1]; ``aspect`` (= width / height) makes them
isotropic before any geometry is computed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import contract as C

EPS = 1e-6

# Which presence key gates each slice of the static (pre-velocity) vector.
_STATIC_DIM = C.FEATURE_DIM - 6  # velocity block is appended after resampling


def _segments() -> list[tuple[int, int, str]]:
    segs, off = [], 0
    for name, size in C.BLOCKS:
        if name == "wrists_velocity":
            break
        if name == "wrists_body":
            segs += [(off, off + 3, "L"), (off + 3, off + 6, "R")]
        elif name == "presence":
            segs.append((off, off + size, "*"))
        else:
            key = {"left_hand_local": "L", "right_hand_local": "R", "pose_body": "P",
                   "two_hand": "LR", "left_angles": "L", "right_angles": "R"}[name]
            segs.append((off, off + size, key))
        off += size
    return segs


SEGMENTS = _segments()
PRESENCE_OFFSET = sum(s for n, s in C.BLOCKS[: [b[0] for b in C.BLOCKS].index("presence")])
WRISTS_BODY_OFFSET = sum(s for n, s in C.BLOCKS[: [b[0] for b in C.BLOCKS].index("wrists_body")])


@dataclass
class FeatureResult:
    features: np.ndarray  # [T, D] float32
    raw_frames: int
    hand_frame_ratio: float
    pose_frame_ratio: float
    status: str  # "ok" | "insufficient_input"
    reasons: list[str] = field(default_factory=list)


def _arr(v, n: int) -> np.ndarray | None:
    if v is None:
        return None
    a = np.asarray(v, dtype=np.float64)
    if a.ndim != 2 or a.shape[0] < n or a.shape[1] < 3:
        raise ValueError(f"landmark array must be [{n}, >=3], got {a.shape}")
    return a[:n, :3].copy()


def _parse(frames: list[dict], aspect: float):
    hands_l, hands_r, poses = [], [], []
    for fr in frames:
        lh = _arr(fr.get("left"), C.HAND_POINTS)
        rh = _arr(fr.get("right"), C.HAND_POINTS)
        po = _arr(fr.get("pose"), 33)
        for a in (lh, rh, po):
            if a is not None:
                a[:, 0] *= aspect
        hands_l.append(lh)
        hands_r.append(rh)
        poses.append(po)
    return hands_l, hands_r, poses


def _hand_scale(h: np.ndarray) -> float:
    return float(max(np.linalg.norm(h[9] - h[0]), EPS))


def _body_frame(hl, hr, po) -> tuple[np.ndarray, float]:
    mids, widths = [], []
    for p in po:
        if p is not None:
            mids.append((p[11] + p[12]) / 2.0)
            widths.append(np.linalg.norm(p[11] - p[12]))
    if mids:
        return np.median(np.stack(mids), axis=0), float(max(np.median(widths), EPS))
    wrists = [h[0] for h in hl + hr if h is not None]
    sizes = [_hand_scale(h) for h in hl + hr if h is not None]
    if not wrists:
        return np.zeros(3), 1.0
    return np.mean(np.stack(wrists), axis=0), float(max(np.median(sizes) * 3.0, EPS))


def _angles(h: np.ndarray) -> np.ndarray:
    out = np.zeros(len(C.FINGER_JOINTS))
    for i, (a, b, c) in enumerate(C.FINGER_JOINTS):
        v1, v2 = h[a] - h[b], h[c] - h[b]
        cos = float(np.dot(v1, v2) / (max(np.linalg.norm(v1) * np.linalg.norm(v2), EPS)))
        out[i] = np.arccos(np.clip(cos, -1.0, 1.0)) / np.pi
    return out


def frame_static(lh, rh, po, origin: np.ndarray, scale: float) -> tuple[np.ndarray, tuple[bool, bool, bool]]:
    v = np.zeros(_STATIC_DIM)
    off = 0
    for h in (lh, rh):
        if h is not None:
            v[off: off + 63] = ((h - h[0]) / _hand_scale(h)).reshape(-1)
        off += 63
    for h in (lh, rh):
        if h is not None:
            v[off: off + 3] = (h[0] - origin) / scale
        off += 3
    if po is not None:
        v[off: off + 27] = ((po[C.POSE_KEEP] - origin) / scale).reshape(-1)
    off += 27
    if lh is not None and rh is not None:
        v[off] = np.linalg.norm(lh[0] - rh[0]) / scale
        for k, t in enumerate(C.FINGERTIPS):
            v[off + 1 + k] = np.linalg.norm(lh[t] - rh[t]) / scale
    off += 6
    for h in (lh, rh):
        if h is not None:
            v[off: off + 15] = _angles(h)
        off += 15
    pres = (lh is not None, rh is not None, po is not None)
    v[off: off + 3] = [float(p) for p in pres]
    return v, pres


def _resample(static: np.ndarray, pres: np.ndarray, T: int) -> np.ndarray:
    n = static.shape[0]
    out = np.zeros((T, _STATIC_DIM))
    for t in range(T):
        s = t * (n - 1) / (T - 1) if n > 1 else 0.0
        i0 = int(np.floor(s))
        i1 = min(i0 + 1, n - 1)
        w = s - i0
        p0, p1 = pres[i0], pres[i1]
        for a, b, key in SEGMENTS:
            if key == "*":
                continue
            ok0 = _ok(p0, key)
            ok1 = _ok(p1, key)
            if ok0 and ok1:
                out[t, a:b] = (1 - w) * static[i0, a:b] + w * static[i1, a:b]
            elif ok0:
                out[t, a:b] = static[i0, a:b]
            elif ok1:
                out[t, a:b] = static[i1, a:b]
        for k in range(3):
            out[t, PRESENCE_OFFSET + k] = 1.0 if (p0[k] or p1[k]) else 0.0
    return out


def _ok(p, key: str) -> bool:
    if key == "L":
        return bool(p[0])
    if key == "R":
        return bool(p[1])
    if key == "P":
        return bool(p[2])
    if key == "LR":
        return bool(p[0] and p[1])
    raise KeyError(key)


# --------------------------------------------------------------------------- face block (contract 2.0.0)
_FI = {n: i for i, n in enumerate(C.FACE_NAMES)}


def face_static(face) -> np.ndarray | None:
    """One frame's face block without presence: 22 points (x, y) around the nose tip, scaled by the
    eye-corner distance, then 6 derived measures. ``face`` is the 22-point subset (already aspect-corrected)."""
    if face is None:
        return None
    f = face[:, :2]
    iod = float(max(np.linalg.norm(f[_FI["l_eye_out"]] - f[_FI["r_eye_out"]]), EPS))
    pts = ((f - f[_FI["nose_tip"]]) / iod).reshape(-1)

    def d(a, b):
        return float(np.linalg.norm(f[_FI[a]] - f[_FI[b]]) / iod)
    derived = [d("lip_top_in", "lip_bottom_in"), d("mouth_l", "mouth_r"), d("l_brow_mid", "l_eye_top"),
               d("r_brow_mid", "r_eye_top"), d("l_eye_top", "l_eye_bottom"), d("r_eye_top", "r_eye_bottom")]
    return np.concatenate([pts, derived])


def face_block(frames: list[dict], aspect: float, T: int) -> tuple[np.ndarray, float]:
    """[T, FACE_DIM] face features resampled like the other blocks; returns also the face frame ratio."""
    n = len(frames)
    k = C.FACE_DIM - 1
    raw, pres = np.zeros((n, k)), np.zeros(n, dtype=bool)
    for i, fr in enumerate(frames):
        a = _arr(fr.get("face"), len(C.FACE_KEEP))
        if a is not None:
            a[:, 0] *= aspect
            raw[i], pres[i] = face_static(a), True
    out = np.zeros((T, C.FACE_DIM))
    for t in range(T):
        s = t * (n - 1) / (T - 1) if n > 1 else 0.0
        i0 = int(np.floor(s))
        i1 = min(i0 + 1, n - 1)
        w = s - i0
        if pres[i0] and pres[i1]:
            out[t, :k] = (1 - w) * raw[i0] + w * raw[i1]
        elif pres[i0]:
            out[t, :k] = raw[i0]
        elif pres[i1]:
            out[t, :k] = raw[i1]
        out[t, k] = 1.0 if (pres[i0] or pres[i1]) else 0.0
    return out, float(pres.mean()) if n else 0.0


def extract_features(frames: list[dict], aspect: float = 1.0, version: str = C.CONTRACT_VERSION) -> FeatureResult:
    """Compute the feature tensor of contract ``version`` (1.0.0, or 2.0.0 with the face block)."""
    if version == C.CONTRACT_V2_VERSION:
        base = extract_features(frames, aspect, C.CONTRACT_VERSION)
        fb, _ = face_block(frames, aspect, C.SEQUENCE_LENGTH) if frames else (np.zeros((C.SEQUENCE_LENGTH, C.FACE_DIM)), 0.0)
        return FeatureResult(np.concatenate([base.features, fb.astype(np.float32)], axis=1), base.raw_frames,
                             base.hand_frame_ratio, base.pose_frame_ratio, base.status, base.reasons)
    C.dim_for(version)
    if aspect <= 0:
        raise ValueError("aspect must be positive")
    T = C.SEQUENCE_LENGTH
    reasons: list[str] = []
    n = len(frames)
    if n == 0:
        return FeatureResult(np.zeros((T, C.FEATURE_DIM), np.float32), 0, 0.0, 0.0,
                             "insufficient_input", ["no frames"])
    hl, hr, po = _parse(frames, aspect)
    origin, scale = _body_frame(hl, hr, po)
    static = np.zeros((n, _STATIC_DIM))
    pres = np.zeros((n, 3), dtype=bool)
    for i in range(n):
        static[i], pres[i] = frame_static(hl[i], hr[i], po[i], origin, scale)
    hand_ratio = float(np.mean(pres[:, 0] | pres[:, 1]))
    pose_ratio = float(np.mean(pres[:, 2]))
    res = _resample(static, pres, T)
    vel = np.zeros((T, 6))
    w = WRISTS_BODY_OFFSET
    for t in range(1, T):
        for side, k in ((0, 0), (1, 3)):
            if res[t, PRESENCE_OFFSET + side] and res[t - 1, PRESENCE_OFFSET + side]:
                vel[t, k: k + 3] = res[t, w + k: w + k + 3] - res[t - 1, w + k: w + k + 3]
    feats = np.concatenate([res, vel], axis=1).astype(np.float32)
    if n < C.MIN_RAW_FRAMES:
        reasons.append(f"only {n} frames (minimum {C.MIN_RAW_FRAMES})")
    if hand_ratio < C.MIN_HAND_FRAME_RATIO:
        reasons.append(f"hands visible in {hand_ratio:.0%} of frames (minimum {C.MIN_HAND_FRAME_RATIO:.0%})")
    status = "insufficient_input" if reasons else "ok"
    return FeatureResult(feats, n, hand_ratio, pose_ratio, status, reasons)
