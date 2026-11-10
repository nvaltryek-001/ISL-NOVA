"""SYNTHETIC landmark fixtures for code smoke tests ONLY.

These are procedurally generated hand trajectories. They are NOT Indian Sign
Language, carry class ids ``SYN01..`` (never ``ISLxxx``), and every artefact
trained on them is flagged ``synthetic: true`` so it can never be promoted or
reported as project performance.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .data import save_landmarks

SYN_LICENSE = "synthetic-test-only"


def _hand(center: np.ndarray, curl: float, rot: float, size: float) -> np.ndarray:
    pts = np.zeros((21, 3))
    pts[0] = center
    base_angles = np.deg2rad([-60, -25, 0, 20, 40]) + rot
    for f in range(5):
        a = base_angles[f]
        d = np.array([np.sin(a), -np.cos(a), 0.0])
        for j in range(4):
            bend = curl * j * 0.35
            dj = np.array([np.sin(a + bend), -np.cos(a + bend), -0.02 * j])
            pts[1 + f * 4 + j] = center + size * (0.45 * d + 0.22 * (j + 1) * dj)
    return pts


def make_sequence(cls: int, rng: np.random.Generator, n_frames: int = 40, signer_scale: float = 1.0,
                  signer_offset: np.ndarray | None = None, two_hands: bool | None = None) -> list[dict]:
    off = signer_offset if signer_offset is not None else np.zeros(3)
    two = (cls % 3 == 0) if two_hands is None else two_hands
    freq = 1 + (cls % 4)
    phase = cls * 0.7
    curl = (cls % 5) / 4.0
    frames = []
    for i in range(n_frames):
        t = i / (n_frames - 1)
        cx = 0.55 + 0.12 * np.cos(2 * np.pi * freq * t / 2 + phase) * signer_scale
        cy = 0.55 + 0.10 * np.sin(2 * np.pi * freq * t / 2 + phase) * signer_scale
        r = _hand(np.array([cx, cy, 0.0]) + off, curl * (0.6 + 0.4 * t), 0.3 * np.sin(phase + t), 0.08 * signer_scale)
        r += rng.normal(0, 0.002, r.shape)
        pose = np.zeros((33, 4))
        pose[:, 3] = 1.0
        pose[0, :3] = [0.5, 0.25, 0]
        pose[11, :3] = [0.62, 0.42, 0]
        pose[12, :3] = [0.38, 0.42, 0]
        pose[13, :3] = [0.66, 0.55, 0]
        pose[14, :3] = [0.34, 0.55, 0]
        pose[16, :3] = r[0]
        pose[23, :3] = [0.58, 0.8, 0]
        pose[24, :3] = [0.42, 0.8, 0]
        pose[:, :3] += off
        pose[:, :2] = 0.5 + (pose[:, :2] - 0.5) * signer_scale
        left = None
        if two:
            left = _hand(np.array([1.0 - cx, cy, 0.0]) + off, curl, -0.2, 0.08 * signer_scale)
            pose[15, :3] = left[0]
        frames.append({"right": r.tolist(), "left": None if left is None else left.tolist(), "pose": pose.tolist()})
    return frames


def write_synthetic_dataset(root: Path, n_classes: int = 6, n_signers: int = 6, reps: int = 4,
                            seed: int = 7, unknown_classes: int = 2) -> dict:
    """Write landmark files + manifest. Extra ``unknown`` classes go to an open-set file."""
    rng = np.random.default_rng(seed)
    root.mkdir(parents=True, exist_ok=True)
    entries, unknown = [], []
    for s in range(n_signers):
        scale = 0.85 + 0.3 * rng.random()
        offset = np.array([rng.uniform(-0.04, 0.04), rng.uniform(-0.04, 0.04), 0])
        for c in range(n_classes + unknown_classes):
            for k in range(reps):
                frames = make_sequence(c, rng, int(rng.integers(30, 50)), scale, offset)
                rid = f"syn_s{s:02d}_c{c:02d}_{k}"
                rel = f"landmarks/{rid}.npz"
                sha = save_landmarks(root / rel, frames, 4 / 3)
                e = {"recording_id": rid, "sign_id": f"SYN{c + 1:02d}", "signer_id": f"syn-signer-{s:02d}",
                     "session_id": f"syn-session-{s:02d}-{k % 2}", "landmarks_path": rel, "sha256": sha,
                     "source": "synthetic", "license": SYN_LICENSE, "approved": True}
                (unknown if c >= n_classes else entries).append(e)
    manifest = {"synthetic": True, "warning": "NOT ISL DATA - code smoke test only", "entries": entries,
                "open_set_entries": unknown}
    import json
    (root / "manifest.json").write_text(json.dumps(manifest, indent=1))
    return manifest
