"""Feature-space augmentation applied to normalised-contract tensors.

Only label-preserving, signer-variation-like transforms are used: global scale,
small in-plane rotation of body-frame coordinates, temporal shift and additive
noise. Horizontal mirroring is deliberately NOT used because left/right hand
roles can be lexically meaningful in ISL.
"""

from __future__ import annotations

import numpy as np

from . import contract as C
from .features import PRESENCE_OFFSET


def _block_slices():
    off, out = 0, {}
    for name, size in C.BLOCKS:
        out[name] = slice(off, off + size)
        off += size
    return out


SL = _block_slices()


def augment_batch(X: np.ndarray, rng: np.random.Generator, noise: float = 0.01,
                  scale: float = 0.08, rot_deg: float = 8.0, max_shift: int = 2) -> np.ndarray:
    X = X.copy()
    B, T, _ = X.shape
    for b in range(B):
        s = 1.0 + rng.uniform(-scale, scale)
        th = np.deg2rad(rng.uniform(-rot_deg, rot_deg))
        R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
        for name in ("wrists_body", "pose_body", "wrists_velocity"):
            blk = X[b, :, SL[name]].reshape(T, -1, 3)
            blk[..., :2] = blk[..., :2] @ R.T
            X[b, :, SL[name]] = (blk * s).reshape(T, -1)
        X[b, :, SL["two_hand"]] *= s
        shift = int(rng.integers(-max_shift, max_shift + 1))
        if shift:
            X[b] = np.roll(X[b], shift, axis=0)
        mask = np.ones(X.shape[2], dtype=bool)
        mask[PRESENCE_OFFSET: PRESENCE_OFFSET + 3] = False
        X[b][:, mask] += rng.normal(0, noise, (T, int(mask.sum()))).astype(X.dtype)
    return X


# --- raw landmark-level augmentation (ISL NOVA v2) ---------------------------
# Live capture differs from studio video: the browser may track at 8-15 fps
# instead of 25, the capture window starts and ends at arbitrary points of the
# sign, and the hand detector misses frames. These transforms simulate that on
# the raw landmark sequence, before the feature contract resamples it.

def raw_variant(frames: list[dict], rng: np.random.Generator, src_fps: float = 25.0,
                fps_range: tuple[float, float] = (8.0, 30.0), crop: float = 0.15,
                miss_max: float = 0.15) -> list[dict]:
    n = len(frames)
    if n < 4:
        return [dict(f) for f in frames]
    # 1) temporal crop: start late / stop early by up to `crop` of the clip
    a = int(rng.uniform(0, crop) * n)
    b = n - int(rng.uniform(0, crop) * n)
    seq = frames[a:max(b, a + 4)]
    # 2) frame-rate simulation: keep frames at a random target rate with random phase
    target = float(rng.uniform(*fps_range))
    if target < src_fps:
        step = src_fps / target
        pos = rng.uniform(0, step)
        idx = []
        while pos < len(seq):
            idx.append(int(pos))
            pos += step
        seq = [seq[i] for i in idx] or seq[:1]
    # 3) missed hand detections
    p = float(rng.uniform(0, miss_max))
    out = []
    for f in seq:
        g = dict(f)
        for side in ("left", "right"):
            if g.get(side) is not None and rng.random() < p:
                g[side] = None
        out.append(g)
    return out
