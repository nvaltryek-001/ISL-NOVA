"""Writes/validates the cross-language parity fixture for the feature contract.

The fixture (frontend/tests/fixtures/feature_parity.json) holds raw frames and
the Python feature output. frontend/tests/features.test.ts recomputes the
features with the TypeScript port and asserts equality, so training (Python)
and in-browser preprocessing (TypeScript) cannot silently diverge.
Regenerate with:  ISL_NOVA_WRITE_FIXTURE=1 pytest ml/tests/test_feature_parity_fixture.py
"""

import json
import os
from pathlib import Path

import numpy as np

from isl_nova_ml import contract as C
from isl_nova_ml.features import extract_features
from isl_nova_ml.synthetic import make_sequence

FIXTURE = Path(__file__).resolve().parents[2] / "frontend" / "tests" / "fixtures" / "feature_parity.json"


def _cases():
    rng = np.random.default_rng(42)
    two = make_sequence(3, rng, 23, 1.1)
    one = make_sequence(1, rng, 37, 0.9)
    # drop some hands/pose to exercise missing-data paths
    gappy = [dict(f) for f in make_sequence(4, rng, 30)]
    for i in range(0, 30, 4):
        gappy[i]["right"] = None
    for i in range(5, 12):
        gappy[i]["pose"] = None
    nopose = [dict(f, pose=None) for f in make_sequence(6, rng, 20)]
    return [("two_hands", two, 4 / 3), ("one_hand", one, 16 / 9), ("gaps", gappy, 1.0), ("no_pose", nopose, 0.75)]


def test_fixture_matches_python_features():
    cases = []
    for name, frames, aspect in _cases():
        r = extract_features(frames, aspect)
        frames_r = [{k: (None if v is None else np.round(np.array(v), 6).tolist()) for k, v in f.items()} for f in frames]
        r = extract_features(frames_r, aspect)
        cases.append({"name": name, "aspect": aspect, "frames": frames_r, "status": r.status,
                      "features": np.round(r.features.astype(np.float64), 6).tolist()})
    payload = {"contract": C.CONTRACT_NAME, "feature_dim": C.FEATURE_DIM, "cases": cases}
    if os.environ.get("ISL_NOVA_WRITE_FIXTURE") or not FIXTURE.exists():
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(payload, separators=(",", ":")))
    stored = json.loads(FIXTURE.read_text())
    assert stored["contract"] == C.CONTRACT_NAME, "contract changed: regenerate fixture"
    for a, b in zip(stored["cases"], cases, strict=True):
        assert np.allclose(np.array(a["features"]), np.array(b["features"]), atol=2e-5), a["name"]
