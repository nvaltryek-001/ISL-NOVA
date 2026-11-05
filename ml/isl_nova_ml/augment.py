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
