"""v3 ML: new architectures in the training pipeline, the "__other__" class, ensembles and the
production unknown-sign detector (all on SYNTHETIC data: plumbing only, no accuracy claims)."""
import json
from pathlib import Path

import numpy as np
import pytest
from isl_nova_ml.inference import Predictor
from isl_nova_ml.openset import OTHER_ID, unknown_part
from isl_nova_ml.registry import Registry
from isl_nova_ml.synthetic import write_synthetic_dataset
from isl_nova_ml.train import build_ensemble, run


def _glosses():
    names, parts = [], {}
    i = 0
    while len(names) < 9 or {"A1", "A2", "B"} - set(parts.values()):
        g = f"oov{i}"
        names.append(g)
        parts[g] = unknown_part(g)
        i += 1
    return names


@pytest.fixture(scope="module")
def v3(tmp_path_factory):
    root = tmp_path_factory.mktemp("v3")
    write_synthetic_dataset(root / "data", n_classes=4, n_signers=5, reps=3)
    man_path = root / "data" / "manifest.json"
    m = json.loads(man_path.read_text())
    names = _glosses()
    m["open_set_entries"] = [dict(e, open_set=True, gloss=names[i % len(names)]) for i, e in enumerate(m["open_set_entries"])]
    man_path.write_text(json.dumps(m))
    res = {}
    for kind in ("tcn", "transformer", "bilstm_attn"):
        res[kind] = run({"model": kind, "hidden": 16, "epochs": 3, "other_class": True, "raw_aug_copies": 1},
                        man_path, root / "data", root / "reg", None, "synthetic")
    return root, res


def test_other_class_training_and_part_b_report(v3):
    root, res = v3
    for r in res.values():
        info = json.loads((Path(r["dir"]) / "model.json").read_text())
        assert info["classes"][-1]["sign_id"] == OTHER_ID
        met = json.loads((Path(r["dir"]) / "metrics.json").read_text())
        b = met["open_set_part_b"]
        assert b["n_unknown"] > 0 and 0 <= b["false_acceptance"] <= 1
        assert met["open_set"] is None  # all-unknown report would include A1 (trained on)


def test_ensemble_calibration_and_predictor(v3, tmp_path):
    from isl_nova_ml.include_pipeline import main

    root, res = v3
    ens = build_ensemble([Path(r["dir"]) for r in res.values()], root / "data" / "manifest.json", root / "data",
                         root / "reg", allow_synthetic=True)
    assert ens["model_id"].startswith("syn-ensemble-")
    reg = Registry(root / "reg")
    reg.promote(ens["model_id"], allow_synthetic=True)
    assert main(["calibrate-open-set", "--registry", str(root / "reg"), "--manifest", str(root / "data" / "manifest.json"),
                 "--data-root", str(root / "data"), "--out", str(tmp_path)]) == 0
    rep = json.loads((tmp_path / "open_set_v3.json").read_text())
    assert rep["has_other_class"] is True
    assert rep["counts"]["unknown_A2"] > 0 and rep["counts"]["unknown_B"] > 0
    for rule in ("max_probability_rule", "open_set_detector_rule"):
        assert 0 <= rep[rule]["false_acceptance"] <= 1 and 0 <= rep[rule]["false_rejection"] <= 1
    pred = Predictor.from_registry(root / "reg")  # integrity still holds after writing the detector
    assert pred.detector and pred.describe()["decision_rule"] == "open_set_detector"
    assert len(pred.vocabulary) == 4 and pred.other_col == 4
    p = np.full(5, 0.02)
    p[4] = 0.92
    assert pred.state_for(p)[0] == "unknown"
    out = pred.decide(p, 5, {}, 0.0)
    assert OTHER_ID not in [t["sign_id"] for t in out["top"]] and len(out["top"]) == 4
    p = np.full(5, 0.01)
    p[0] = 0.96
    assert pred.state_for(p)[0] in ("recognized", "uncertain")
