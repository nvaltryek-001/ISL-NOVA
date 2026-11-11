"""Feature contract 2.0.0: the 204 features of 1.0.0 plus a 51-value face (non-manual) block."""
import json

import numpy as np
import pytest
from isl_nova_ml import contract as C
from isl_nova_ml.data import load_landmarks, save_landmarks
from isl_nova_ml.features import extract_features, face_static


def _frames(n=20, face=True, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        hand = (rng.normal(0.5, 0.05, (21, 3))).tolist()
        pose = np.c_[rng.normal(0.5, 0.1, (33, 3)), np.ones(33)].tolist()
        f = {"left": hand, "right": None, "pose": pose}
        if face and i % 5 != 4:  # some frames without a face
            pts = rng.normal(0.5, 0.02, (22, 3))
            pts[C.FACE_NAMES.index("l_eye_out"), :2] = [0.45, 0.4]
            pts[C.FACE_NAMES.index("r_eye_out"), :2] = [0.55, 0.4]
            f["face"] = pts.tolist()
        out.append(f)
    return out


def test_contract_dimensions():
    assert C.FACE_DIM == 22 * 2 + 6 + 1 == 51
    assert C.dim_for("1.0.0") == 204 and C.dim_for("2.0.0") == 255
    assert C.name_for("2.0.0") == "isl-nova-fc-2.0.0"
    with pytest.raises(ValueError):
        C.dim_for("9.9.9")


def test_v2_keeps_v1_features_and_appends_the_face_block():
    fr = _frames()
    v1 = extract_features(fr, 4 / 3)
    v2 = extract_features(fr, 4 / 3, "2.0.0")
    assert v1.features.shape == (32, 204) and v2.features.shape == (32, 255)
    np.testing.assert_array_equal(v2.features[:, :204], v1.features)
    assert v2.features[:, -1].max() == 1.0  # face presence
    no_face = extract_features(_frames(face=False), 4 / 3, "2.0.0")
    assert np.all(no_face.features[:, 204:] == 0)


def test_face_measures_are_scale_and_position_invariant():
    rng = np.random.default_rng(3)
    f = rng.normal(0.5, 0.03, (22, 3))
    g = f.copy()
    g[:, :2] = g[:, :2] * 1.7 + 0.2  # same face, bigger and moved
    np.testing.assert_allclose(face_static(f), face_static(g), rtol=1e-9, atol=1e-12)


def test_landmark_files_keep_the_face(tmp_path):
    fr = _frames()
    save_landmarks(tmp_path / "x.npz", fr, 4 / 3)
    back, aspect = load_landmarks(tmp_path / "x.npz")
    assert aspect == pytest.approx(4 / 3)
    assert back[0]["face"] is not None and back[4]["face"] is None
    np.testing.assert_allclose(back[0]["face"], fr[0]["face"], rtol=1e-6)
    save_landmarks(tmp_path / "y.npz", _frames(face=False), 1.0)
    assert "face" not in load_landmarks(tmp_path / "y.npz")[0][0]


def test_training_and_prediction_with_contract_2(tmp_path):
    from isl_nova_ml.inference import Predictor
    from isl_nova_ml.registry import Registry
    from isl_nova_ml.synthetic import write_synthetic_dataset
    from isl_nova_ml.train import run

    write_synthetic_dataset(tmp_path / "data", n_classes=3, n_signers=4, reps=2, unknown_classes=0)
    m = json.loads((tmp_path / "data" / "manifest.json").read_text())
    for e in m["entries"]:  # add faces to the landmark files
        p = tmp_path / "data" / e["landmarks_path"]
        frames, aspect = load_landmarks(p)
        faces = _frames(len(frames), seed=hash(e["recording_id"]) % 1000)
        for f, g in zip(frames, faces, strict=True):
            f["face"] = g.get("face")
        save_landmarks(p, frames, aspect)
    res = run({"model": "lstm", "hidden": 8, "epochs": 2, "contract_version": "2.0.0"},
              tmp_path / "data" / "manifest.json", tmp_path / "data", tmp_path / "reg", None, "synthetic")
    info = json.loads((tmp_path / "reg" / res["model_id"] / "model.json").read_text())
    assert info["contract"] == {"name": "isl-nova-fc-2.0.0", "version": "2.0.0", "feature_dim": 255, "sequence_length": 32}
    Registry(tmp_path / "reg").promote(res["model_id"], allow_synthetic=True)
    pred = Predictor.from_registry(tmp_path / "reg")
    assert pred.needs_face and pred.describe()["needs_face"] is True
    out = pred.predict(_frames(), 4 / 3)
    assert out["state"] in ("recognized", "uncertain", "unknown")
