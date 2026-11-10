"""Practice Coach scoring and reference animation (with a small reference file built from synthetic data)."""
import numpy as np
from app.main import create_app
from isl_nova_ml import contract as C
from isl_nova_ml.features import extract_features
from isl_nova_ml.synthetic import make_sequence
from starlette.testclient import TestClient

from tests.conftest import make_settings

A = "/api/v1"


def _seq(cls, seed):
    return make_sequence(cls, np.random.default_rng(seed), 40)


def _write_refs(d):
    ids, T, frames = ["ISL001", "ISL002"], [], []
    for c in (1, 2):
        T.append(np.mean([extract_features(_seq(c, s), 4 / 3).features for s in range(5)], 0))
        frames.append(_seq(c, 99))
    L = max(len(f) for f in frames)
    arr = {k: np.zeros((2, L, n, dd), np.float16) for k, n, dd in (("left", 21, 3), ("right", 21, 3), ("pose", 33, 4))}
    msk = {k: np.zeros((2, L), bool) for k in arr}
    for i, fr in enumerate(frames):
        for t, f in enumerate(fr):
            for k in arr:
                if f.get(k) is not None:
                    arr[k][i, t] = np.asarray(f[k])
                    msk[k][i, t] = True
    def dist(cls, seed, i):
        return float(np.sqrt(np.mean((extract_features(_seq(cls, seed), 4 / 3).features - T[i]) ** 2)))
    same = [np.median([dist(c, s, i) for s in range(10, 15)]) for i, c in enumerate((1, 2))]
    other = [np.median([dist(2 if c == 1 else 1, s, i) for s in range(10, 15)]) for i, c in enumerate((1, 2))]
    d.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(d / "references_v1.npz", sign_ids=np.array(ids), templates=np.array(T, np.float16),
                        same_median=np.array(same, np.float32), other_median=np.array(other, np.float32),
                        block_same_median=np.full((2, len(C.BLOCKS)), 0.2, np.float32),
                        block_names=np.array([b for b, _ in C.BLOCKS]), lengths=np.array([len(f) for f in frames]),
                        **arr, **{f"{k}_mask": v for k, v in msk.items()})


def test_practice_unavailable_without_references(tmp_path):
    s = make_settings(tmp_path, references_dir=tmp_path / "none")
    with TestClient(create_app(s)) as c:
        assert c.get(f"{A}/practice/status").json()["available"] is False
        assert c.get(f"{A}/practice/reference/ISL001").status_code == 503


def test_practice_reference_and_scoring(tmp_path):
    s = make_settings(tmp_path, references_dir=tmp_path / "refs")
    _write_refs(tmp_path / "refs")
    with TestClient(create_app(s)) as c:
        st = c.get(f"{A}/practice/status").json()
        assert st["available"] and st["classes"] == 2
        ref = c.get(f"{A}/practice/reference/ISL001").json()
        assert ref["frames"] and ref["label"] == "Alright" and "INCLUDE" in ref["attribution"]
        assert c.get(f"{A}/practice/reference/ISL150").status_code == 404
        same = c.post(f"{A}/practice/score", json={"sign_id": "ISL001", "frames": _seq(1, 7), "aspect": 4 / 3}).json()
        other = c.post(f"{A}/practice/score", json={"sign_id": "ISL001", "frames": _seq(2, 7), "aspect": 4 / 3}).json()
        assert same["state"] == "scored" and other["state"] == "scored"
        assert same["score"] > other["score"], (same["score"], other["score"])
        assert len(same["parts"]) == len(C.BLOCKS) and same["tips"]
        empty = c.post(f"{A}/practice/score", json={"sign_id": "ISL001", "frames": []}).json()
        assert empty["state"] == "insufficient_input" and empty["score"] is None
