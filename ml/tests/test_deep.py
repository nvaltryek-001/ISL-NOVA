"""Numerical gradient checks for the hand-written backward passes in deep.py."""
import numpy as np
import pytest
from isl_nova_ml.deep import BiLSTMAttnClassifier, EnsembleModel, TCNClassifier, TransformerClassifier
from isl_nova_ml.models import load_model, save_model


def _gradcheck(model, B=3, T=7, eps=1e-6):
    rng = np.random.default_rng(0)
    X = rng.normal(size=(B, T, model.D))
    y = rng.integers(0, model.C, B)
    w = rng.uniform(0.5, 1.5, B)
    _, g = model.loss_and_grads(X, y, w)
    assert set(g) == set(model.p), set(model.p) ^ set(g)
    worst = 0.0
    for k, P in model.p.items():
        flat = P.reshape(-1)
        idx = rng.choice(flat.size, size=min(6, flat.size), replace=False)
        for j in idx:
            old = flat[j]
            flat[j] = old + eps
            lp = model.loss_and_grads(X, y, w)[0]
            flat[j] = old - eps
            lm = model.loss_and_grads(X, y, w)[0]
            flat[j] = old
            num = (lp - lm) / (2 * eps)
            ana = g[k].reshape(-1)[j]
            rel = abs(num - ana) / max(1e-7, abs(num) + abs(ana))
            if abs(num - ana) > 1e-7:
                worst = max(worst, rel)
                assert rel < 1e-4, (k, j, num, ana)
    return worst


@pytest.mark.parametrize("cls", [TCNClassifier, TransformerClassifier, BiLSTMAttnClassifier])
def test_gradients_match_numerical(cls):
    m = cls(5, 4, hidden=8, seed=1)
    _gradcheck(m)


@pytest.mark.parametrize("cls", [TCNClassifier, TransformerClassifier, BiLSTMAttnClassifier])
def test_learns_a_separable_toy_task_and_round_trips(cls, tmp_path):
    rng = np.random.default_rng(3)
    X = rng.normal(size=(120, 10, 6))
    y = (X[:, :, 0].mean(1) > 0).astype(int) + 2 * (X[:, :, 1].mean(1) > 0).astype(int)
    m = cls(6, 4, hidden=16, seed=2)
    m.norm.fit(X)
    opt = m.make_optimizer(0.01, 0.0)
    w = np.ones(len(y))
    for _ in range(40):
        m.train_epoch(X, y, w, opt, 32, rng)
    acc = (m.predict_proba(X).argmax(1) == y).mean()
    assert acc > 0.85, acc
    m.temperature = 1.3
    save_model(m, tmp_path / "m")
    m2 = load_model(tmp_path / "m")
    np.testing.assert_allclose(m2.predict_proba(X[:5]), m.predict_proba(X[:5]), rtol=1e-6)


def test_ensemble_saves_one_file_and_matches(tmp_path):
    rng = np.random.default_rng(4)
    X = rng.normal(size=(8, 10, 6))
    members = []
    for cls in (TCNClassifier, TransformerClassifier):
        m = cls(6, 3, hidden=8, seed=5)
        m.norm.fit(X)
        members.append(m)
    e = EnsembleModel(members)
    e.temperature = 0.9
    P = e.predict_proba(X)
    np.testing.assert_allclose(P.sum(1), 1.0)
    save_model(e, tmp_path / "e")
    assert sorted(p.name for p in (tmp_path / "e").iterdir()) == ["architecture.json", "weights.npz"]
    np.testing.assert_allclose(load_model(tmp_path / "e").predict_proba(X), P, rtol=1e-6)
