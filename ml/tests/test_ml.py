import json
from pathlib import Path

import numpy as np
import pytest
from isl_nova_ml import contract as C
from isl_nova_ml.data import (
    ManifestError,
    assign_splits,
    leakage_report,
    load_landmarks,
    load_manifest,
    save_landmarks,
    training_eligible,
)
from isl_nova_ml.features import extract_features
from isl_nova_ml.inference import ModelUnavailable, Predictor, StreamSmoother
from isl_nova_ml.metrics import auroc, classification_report, expected_calibration_error, topk_accuracy
from isl_nova_ml.models import (
    DTW1NN,
    GRUClassifier,
    LSTMClassifier,
    PooledLogReg,
    dtw_batch,
    dtw_distance,
    load_model,
    save_model,
    softmax,
)
from isl_nova_ml.registry import Registry, RegistryError
from isl_nova_ml.synthetic import make_sequence, write_synthetic_dataset
from isl_nova_ml.train import TrainingError, run

RNG = np.random.default_rng(0)


def seq(cls=1, n=40, **kw):
    return make_sequence(cls, np.random.default_rng(cls), n, **kw)


# --- feature contract -------------------------------------------------------

def test_contract_dimensions_and_names():
    d = C.as_dict()
    assert d["feature_dim"] == 204 == C.FEATURE_DIM
    assert len(d["feature_names"]) == C.FEATURE_DIM
    assert len(set(d["feature_names"])) == C.FEATURE_DIM, "feature names must be unique"
    assert d["feature_names"][0] == "left_hand_0_x"
    assert d["feature_names"][-1] == "right_wrist_vel_z"


def test_feature_shape_dtype_and_status():
    r = extract_features(seq(), 4 / 3)
    assert r.features.shape == (C.SEQUENCE_LENGTH, C.FEATURE_DIM)
    assert r.features.dtype == np.float32
    assert r.status == "ok" and np.isfinite(r.features).all()


def test_missing_hand_is_zero_with_presence_flag():
    r = extract_features(seq(cls=1, two_hands=False), 1.0)
    names = C.feature_names()
    li = names.index("left_present")
    assert np.all(r.features[:, li] == 0)
    assert np.all(r.features[:, : 63] == 0)
    assert np.all(r.features[:, names.index("right_present")] == 1)


def test_insufficient_input_states():
    assert extract_features([], 1.0).status == "insufficient_input"
    no_hands = [{"left": None, "right": None, "pose": None}] * 20
    r = extract_features(no_hands, 1.0)
    assert r.status == "insufficient_input" and r.hand_frame_ratio == 0
    short = seq(n=4)
    assert extract_features(short, 1.0).status == "insufficient_input"


def test_translation_and_scale_invariance():
    frames = seq(cls=2)
    shifted = []
    for f in frames:
        g = {}
        for k, v in f.items():
            if v is None:
                g[k] = None
            else:
                a = np.array(v)
                a[:, :2] = (a[:, :2] - 0.5) * 0.8 + 0.5 + 0.03
                a[:, 2] *= 0.8
                g[k] = a.tolist()
        shifted.append(g)
    a = extract_features(frames, 1.0).features
    b = extract_features(shifted, 1.0).features
    assert np.allclose(a, b, atol=2e-4)


def test_bad_landmark_shape_rejected():
    with pytest.raises(ValueError):
        extract_features([{"left": [[0, 0, 0]] * 5, "right": None, "pose": None}] * 10)


def test_landmark_file_roundtrip(tmp_path):
    frames = seq(cls=3)
    save_landmarks(tmp_path / "a.npz", frames, 1.25)
    back, aspect = load_landmarks(tmp_path / "a.npz")
    assert aspect == 1.25 and len(back) == len(frames)
    a = extract_features(frames, 1.25).features
    b = extract_features(back, 1.25).features
    assert np.allclose(a, b, atol=1e-5)


# --- models -----------------------------------------------------------------

@pytest.mark.parametrize("cls", [LSTMClassifier, GRUClassifier])
def test_rnn_gradients_match_finite_differences(cls):
    m = cls(5, 3, hidden=4, seed=1)
    m.p["b"] += RNG.normal(0, 0.1, m.p["b"].shape)
    X = RNG.normal(size=(3, 6, 5))
    y = np.array([0, 2, 1])
    w = np.array([1.0, 2.0, 0.5])
    _, g = m.loss_and_grads(X, y, w)
    for k in m.p:
        idx = tuple(RNG.integers(0, s) for s in m.p[k].shape)
        old = m.p[k][idx]
        m.p[k][idx] = old + 1e-5
        lp, _ = m.loss_and_grads(X, y, w)
        m.p[k][idx] = old - 1e-5
        lm, _ = m.loss_and_grads(X, y, w)
        m.p[k][idx] = old
        num = (lp - lm) / 2e-5
        assert abs(num - g[k][idx]) < 1e-6 + 1e-4 * abs(num), (k, num, g[k][idx])


@pytest.mark.parametrize("kind", ["lstm", "gru", "pooled_logreg", "dtw_1nn"])
def test_checkpoint_roundtrip_is_exact(tmp_path, kind):
    X = RNG.normal(size=(8, C.SEQUENCE_LENGTH, C.FEATURE_DIM)).astype(np.float32)
    y = np.array([0, 1, 2, 0, 1, 2, 0, 1])
    if kind == "lstm":
        m = LSTMClassifier(C.FEATURE_DIM, 3, 6)
        m.norm.fit(X)
    elif kind == "gru":
        m = GRUClassifier(C.FEATURE_DIM, 3, 6)
        m.norm.fit(X)
    elif kind == "pooled_logreg":
        m = PooledLogReg(C.FEATURE_DIM, 3).fit(X, y)
    else:
        m = DTW1NN(C.FEATURE_DIM, 3).fit(X, y)
    m.temperature = 1.7
    save_model(m, tmp_path / "m")
    m2 = load_model(tmp_path / "m")
    assert np.allclose(m.predict_proba(X[:3]), m2.predict_proba(X[:3]))


def test_softmax_and_metrics():
    P = softmax(np.array([[2.0, 1.0, 0.1], [0.1, 0.2, 3.0]]))
    assert np.allclose(P.sum(1), 1)
    y = np.array([0, 2])
    assert topk_accuracy(P, y, 1) == 1.0
    rep = classification_report(P, y, 3)
    assert rep["macro_f1"] == 1.0 and rep["confusion"][0][0] == 1
    assert 0 <= expected_calibration_error(P, y) <= 1
    assert auroc(np.array([0.9, 0.8]), np.array([0.1, 0.2])) == 1.0


# --- data governance -----------------------------------------------------------

def _e(i, signer, session, split=None, **kw):
    e = {"recording_id": f"r{i}", "sign_id": "ISL001", "signer_id": signer, "session_id": session,
         "landmarks_path": f"x/{i}.npz", "source": "local", "license": "project-consent",
         "consent_scope": ["model_training"], "approved": True}
    if split:
        e["split"] = split
    e.update(kw)
    return e


def test_signer_independent_split_has_no_leakage():
    es = [_e(i, f"s{i % 7}", f"sess{i % 7}") for i in range(40)]
    out = assign_splits(es, seed=3)
    assert {e["split"] for e in out} == {"train", "val", "test"}
    assert not leakage_report(out)["has_leakage"]


def test_leakage_is_detected():
    es = [_e(1, "a", "x", "train"), _e(2, "a", "y", "test"), _e(3, "b", "z", "val", sha256="h"),
          _e(4, "c", "w", "train", sha256="h")]
    rep = leakage_report(es)
    assert rep["has_leakage"] and rep["signer_id"] == ["a"] and rep["sha256"] == ["h"]


def test_eligibility_rules():
    assert training_eligible(_e(1, "a", "x"))[0]
    assert not training_eligible(_e(1, "a", "x", approved=False))[0]
    assert not training_eligible(_e(1, "a", "x", consent_scope=["research_display"]))[0]
    assert not training_eligible(_e(1, "a", "x", license="unknown"))[0]


def test_manifest_validation(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"entries": [_e(1, "a", "x"), _e(1, "a", "x")]}))
    with pytest.raises(ManifestError, match="duplicate"):
        load_manifest(p)
    p.write_text(json.dumps({"entries": [{"recording_id": "z"}]}))
    with pytest.raises(ManifestError, match="missing"):
        load_manifest(p)


# --- end-to-end synthetic pipeline -------------------------------------------

@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    root = tmp_path_factory.mktemp("smoke")
    write_synthetic_dataset(root / "data", n_classes=4, n_signers=5, reps=3)
    res = run({"model": "pooled_logreg"}, root / "data" / "manifest.json", root / "data", root / "reg",
              None, "synthetic")
    return root, res


def test_pipeline_flags_synthetic_and_records_lineage(trained):
    root, res = trained
    info = json.loads((Path(res["dir"]) / "model.json").read_text())
    assert info["synthetic"] is True and "NOT ISL" in info["warning"]
    assert info["model_id"].startswith("syn-")
    assert info["contract"]["version"] == C.CONTRACT_VERSION
    lin = info["lineage"]
    assert not set(lin["train_recording_ids"]) & set(lin["test_recording_ids"])
    assert lin["leakage"]["has_leakage"] is False


def test_registry_refuses_synthetic_promotion_and_rolls_back(trained):
    root, res = trained
    reg = Registry(root / "reg")
    with pytest.raises(RegistryError):
        reg.promote(res["model_id"])
    reg.promote(res["model_id"], allow_synthetic=True)
    assert reg.read()["active"] == res["model_id"]
    assert reg.rollback() is None
    assert reg.read()["active"] is None


def test_predictor_states(trained):
    root, res = trained
    p = Predictor(Path(res["dir"]))
    out = p.predict(seq(cls=1), 4 / 3)
    assert out["state"] in {"recognized", "uncertain", "unknown"}
    assert len(out["top"]) == 4 and out["synthetic"] is True
    assert abs(sum(t["probability"] for t in out["top"]) - 1) < 1e-3
    assert p.predict([], 1.0)["state"] == "insufficient_input"
    flat = np.full(4, 0.25)
    assert p.decide(flat, 5, {}, 0.0)["state"] in {"unknown", "uncertain"}


def test_predictor_rejects_tampered_weights(trained):
    root, res = trained
    d = Path(res["dir"])
    w = d / "weights.npz"
    orig = w.read_bytes()
    try:
        w.write_bytes(orig + b"x")
        with pytest.raises(Exception, match="checksum"):
            Predictor(d)
    finally:
        w.write_bytes(orig)


def test_no_active_model_is_unavailable(tmp_path):
    with pytest.raises(ModelUnavailable):
        Predictor.from_registry(tmp_path)


def test_synthetic_cannot_mix_with_real(tmp_path):
    write_synthetic_dataset(tmp_path, n_classes=2, n_signers=3, reps=1, unknown_classes=0)
    m = json.loads((tmp_path / "manifest.json").read_text())
    m["entries"].append(dict(m["entries"][0], recording_id="real", source="local"))
    (tmp_path / "manifest.json").write_text(json.dumps(m))
    with pytest.raises(TrainingError, match="mixed"):
        run({"model": "pooled_logreg"}, tmp_path / "manifest.json", tmp_path, tmp_path / "reg")


def test_stream_smoother():
    s = StreamSmoother(0.5)
    a = s.update(np.array([1.0, 0.0]))
    b = s.update(np.array([0.0, 1.0]))
    assert np.allclose(a, [1, 0]) and np.allclose(b, [0.5, 0.5])
    assert s.update(None) is None and s.state is None


def test_batched_dtw_matches_reference():
    q = RNG.normal(size=(12, 5))
    refs = RNG.normal(size=(7, 12, 5))
    for w in (None, 3):
        got = dtw_batch(q, refs, w)
        want = np.array([dtw_distance(q, r, w) for r in refs])
        assert np.allclose(got, want)


def test_open_set_evaluation_reports_genuine_counts(trained, tmp_path):
    from isl_nova_ml.include_pipeline import main

    root, res = trained
    reg = Registry(root / "reg")
    reg.promote(res["model_id"], allow_synthetic=True)
    m = json.loads((root / "data" / "manifest.json").read_text())
    entries = [dict(e, split="test") for e in m["entries"]]
    unknown = [dict(e, open_set=True, gloss=e["sign_id"]) for e in m["open_set_entries"]]
    assert unknown, "synthetic fixture must contain open-set sequences"
    man = tmp_path / "manifest.json"
    man.write_text(json.dumps({"entries": entries, "open_set_entries": unknown}))
    assert main(["open-set", "--registry", str(root / "reg"), "--manifest", str(man),
                 "--data-root", str(root / "data"), "--out", str(tmp_path / "out")]) == 0
    rep = json.loads((tmp_path / "out" / "open_set.json").read_text())
    assert rep["known_test_sequences"] == len(entries) and rep["unknown_sequences"] == len(unknown)
    assert 0.0 <= rep["auroc_maxprob_known_vs_unknown"] <= 1.0
    assert sum(rep["unknown_states"].values()) == len(unknown)
    assert (tmp_path / "out" / "open_set_rows.csv").exists()
    reg.rollback()


def test_raw_variant_simulates_low_fps_crop_and_misses():
    from isl_nova_ml.augment import raw_variant

    frames = seq(cls=2, n=60)
    rng = np.random.default_rng(1)
    lens = [len(raw_variant(frames, rng)) for _ in range(50)]
    assert min(lens) < 30 < max(lens) <= 60, "frame rate and crop vary the length"
    v = raw_variant(frames, np.random.default_rng(3), fps_range=(10, 10), crop=0.0, miss_max=0.0)
    assert 22 <= len(v) <= 26  # 60 frames at 25 fps -> ~24 at 10 fps
    assert all(set(f) == set(frames[0]) for f in v)
    assert extract_features(v, 4 / 3).features.shape == (C.SEQUENCE_LENGTH, C.FEATURE_DIM)


def test_build_tensors_adds_marked_augmented_copies(tmp_path):
    from isl_nova_ml.data import build_tensors

    write_synthetic_dataset(tmp_path, n_classes=2, n_signers=2, reps=1)
    m = json.loads((tmp_path / "manifest.json").read_text())
    entries = m["entries"]
    cidx = {s: i for i, s in enumerate(sorted({e["sign_id"] for e in entries}))}
    plain = build_tensors(entries, tmp_path, cidx)
    aug = build_tensors(entries, tmp_path, cidx, raw_aug_copies=2, seed=5)
    assert len(aug.y) > len(plain.y)
    assert sum("#aug" not in i for i in aug.ids) == len(plain.ids)


def test_open_set_v2_detectors_and_disjoint_protocol(trained, tmp_path):
    from isl_nova_ml.include_pipeline import main
    from isl_nova_ml.openset import gloss_half

    root, res = trained
    reg = Registry(root / "reg")
    reg.promote(res["model_id"], allow_synthetic=True)
    m = json.loads((root / "data" / "manifest.json").read_text())
    splits = ["train", "train", "val", "test"]
    entries = [dict(e, split=splits[i % 4]) for i, e in enumerate(m["entries"])]
    names = [f"g{i}" for i in range(8)]
    unknown = [dict(e, open_set=True, gloss=names[i % 8]) for i, e in enumerate(m["open_set_entries"])]
    assert {gloss_half(g) for g in names} == {"A", "B"}
    man = tmp_path / "manifest.json"
    man.write_text(json.dumps({"entries": entries, "open_set_entries": unknown}))
    assert main(["open-set-v2", "--registry", str(root / "reg"), "--manifest", str(man),
                 "--data-root", str(root / "data"), "--out", str(tmp_path / "o")]) == 0
    rep = json.loads((tmp_path / "o" / "open_set_v2.json").read_text())
    assert set(rep["detectors"]) == {"maxprob", "margin", "entropy", "centroid", "combined"}
    for d in rep["detectors"].values():
        assert 0 <= d["auroc"] <= 1 and 0 <= d["keep90"]["false_acceptance"] <= 1
    assert rep["counts"]["unknown_A"] > 0 and rep["counts"]["unknown_B"] > 0
    reg.rollback()
