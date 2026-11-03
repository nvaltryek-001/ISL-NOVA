"""Sequence classifiers implemented with NumPy (CPU only, no pickle).

* ``LSTMClassifier`` - baseline (single-layer LSTM, last + mean pooled state).
* ``GRUClassifier``  - comparison recurrent model with the same head.
* ``PooledLogReg``   - non-temporal baseline: temporal statistics + softmax regression.
* ``DTW1NN``         - dynamic-time-warping nearest neighbour reference method.

All models consume ``float32 [N, T, D]`` tensors produced by
``features.extract_features`` and expose ``logits(X)``. Weights are stored as
``.npz`` arrays plus JSON metadata; nothing is unpickled at load time.

TCN and Temporal-Transformer candidates are documented in
research/EXPERIMENT_PROTOCOL.md but not implemented here because they need an
autodiff framework (PyTorch) that was not installable in the build sandbox.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def softmax(z: np.ndarray, axis: int = -1) -> np.ndarray:
    z = z - z.max(axis=axis, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=axis, keepdims=True)


def _sig(x: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + np.tanh(0.5 * x))


class Normalizer:
    def __init__(self, mean: np.ndarray | None = None, std: np.ndarray | None = None):
        self.mean, self.std = mean, std

    def fit(self, X: np.ndarray) -> Normalizer:
        flat = X.reshape(-1, X.shape[-1]).astype(np.float64)
        self.mean = flat.mean(0)
        self.std = np.maximum(flat.std(0), 1e-3)
        return self

    def __call__(self, X: np.ndarray) -> np.ndarray:
        return ((X - self.mean) / self.std).astype(np.float64)


class _Adam:
    def __init__(self, params: dict[str, np.ndarray], lr: float, wd: float = 0.0):
        self.lr, self.wd, self.t = lr, wd, 0
        self.m = {k: np.zeros_like(v) for k, v in params.items()}
        self.v = {k: np.zeros_like(v) for k, v in params.items()}

    def step(self, params, grads, b1=0.9, b2=0.999, eps=1e-8):
        self.t += 1
        for k in params:
            g = grads[k] + (self.wd * params[k] if k.startswith("W") else 0.0)
            self.m[k] = b1 * self.m[k] + (1 - b1) * g
            self.v[k] = b2 * self.v[k] + (1 - b2) * g * g
            mh = self.m[k] / (1 - b1**self.t)
            vh = self.v[k] / (1 - b2**self.t)
            params[k] -= self.lr * mh / (np.sqrt(vh) + eps)


class _RNNBase:
    kind = "rnn"
    gates = 1

    def __init__(self, n_features: int, n_classes: int, hidden: int = 64, seed: int = 0):
        self.D, self.C, self.H, self.seed = n_features, n_classes, hidden, seed
        rng = np.random.default_rng(seed)
        G, H = self.gates, hidden
        s_in, s_h = 1.0 / np.sqrt(n_features), 1.0 / np.sqrt(H)
        self.p: dict[str, np.ndarray] = {
            "Wx": rng.uniform(-s_in, s_in, (n_features, G * H)),
            "Wh": rng.uniform(-s_h, s_h, (H, G * H)),
            "b": np.zeros(G * H),
            "Wo": rng.normal(0, np.sqrt(1.0 / (2 * H)), (2 * H, n_classes)),
            "bo": np.zeros(n_classes),
        }
        self._init_extra()
        self.norm = Normalizer()
        self.temperature = 1.0

    def _init_extra(self):
        pass

    # --- forward/backward over a normalised batch -------------------------
    def _head(self, hs: np.ndarray):
        pooled = np.concatenate([hs[:, -1], hs.mean(1)], axis=1)
        return pooled, pooled @ self.p["Wo"] + self.p["bo"]

    def logits_raw(self, Xn: np.ndarray) -> np.ndarray:
        hs, _ = self._forward(Xn)
        return self._head(hs)[1]

    def loss_and_grads(self, Xn: np.ndarray, y: np.ndarray, w: np.ndarray):
        hs, cache = self._forward(Xn)
        pooled, logits = self._head(hs)
        P = softmax(logits)
        B, T, H = hs.shape
        wn = w / w.sum()
        loss = float(-(wn * np.log(P[np.arange(B), y] + 1e-12)).sum())
        dl = P.copy()
        dl[np.arange(B), y] -= 1.0
        dl *= wn[:, None]
        g = {"Wo": pooled.T @ dl, "bo": dl.sum(0)}
        dp = dl @ self.p["Wo"].T
        dhs = np.repeat((dp[:, H:] / T)[:, None, :], T, axis=1)
        dhs[:, -1] += dp[:, :H]
        g.update(self._backward(Xn, dhs, cache))
        return loss, g

    # --- public API ---------------------------------------------------------
    def logits(self, X: np.ndarray) -> np.ndarray:
        return self.logits_raw(self.norm(X)) / self.temperature

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return softmax(self.logits(X))

    def train_epoch(self, X, y, w, opt: _Adam, batch: int, rng, augment=None, clip: float = 5.0) -> float:
        idx = rng.permutation(len(X))
        tot = 0.0
        for s in range(0, len(idx), batch):
            b = idx[s: s + batch]
            xb = X[b]
            if augment is not None:
                xb = augment(xb, rng)
            loss, g = self.loss_and_grads(self.norm(xb), y[b], w[b])
            gn = np.sqrt(sum(float((v**2).sum()) for v in g.values()))
            if gn > clip:
                g = {k: v * (clip / gn) for k, v in g.items()}
            opt.step(self.p, g)
            tot += loss * len(b)
        return tot / len(X)

    def make_optimizer(self, lr: float, wd: float) -> _Adam:
        return _Adam(self.p, lr, wd)

    def meta(self) -> dict:
        return {"kind": self.kind, "D": self.D, "C": self.C, "H": self.H,
                "seed": self.seed, "temperature": self.temperature}

    def save(self, path: Path) -> None:
        np.savez(path, **self.p, norm_mean=self.norm.mean, norm_std=self.norm.std)

    @classmethod
    def from_saved(cls, meta: dict, path: Path):
        m = cls(meta["D"], meta["C"], meta["H"], meta.get("seed", 0))
        with np.load(path, allow_pickle=False) as z:
            for k in m.p:
                m.p[k] = z[k].astype(np.float64)
            m.norm = Normalizer(z["norm_mean"], z["norm_std"])
        m.temperature = float(meta.get("temperature", 1.0))
        return m


class LSTMClassifier(_RNNBase):
    kind = "lstm"
    gates = 4  # i, f, o, g

    def _init_extra(self):
        self.p["b"][self.H: 2 * self.H] = 1.0  # forget-gate bias

    def _forward(self, X):
        B, T, _ = X.shape
        H = self.H
        h = np.zeros((B, H))
        c = np.zeros((B, H))
        hs = np.zeros((B, T, H))
        cache = []
        for t in range(T):
            z = X[:, t] @ self.p["Wx"] + h @ self.p["Wh"] + self.p["b"]
            i, f, o = _sig(z[:, :H]), _sig(z[:, H:2 * H]), _sig(z[:, 2 * H:3 * H])
            gg = np.tanh(z[:, 3 * H:])
            c_prev, h_prev = c, h
            c = f * c + i * gg
            tc = np.tanh(c)
            h = o * tc
            hs[:, t] = h
            cache.append((i, f, o, gg, c_prev, h_prev, tc))
        return hs, cache

    def _backward(self, X, dhs, cache):
        B, T, _ = X.shape
        H = self.H
        dWx, dWh, db = np.zeros_like(self.p["Wx"]), np.zeros_like(self.p["Wh"]), np.zeros_like(self.p["b"])
        dh_next = np.zeros((B, H))
        dc_next = np.zeros((B, H))
        for t in reversed(range(T)):
            i, f, o, gg, c_prev, h_prev, tc = cache[t]
            dh = dhs[:, t] + dh_next
            do = dh * tc * o * (1 - o)
            dc = dh * o * (1 - tc**2) + dc_next
            di = dc * gg * i * (1 - i)
            dgg = dc * i * (1 - gg**2)
            df = dc * c_prev * f * (1 - f)
            dz = np.concatenate([di, df, do, dgg], axis=1)
            dWx += X[:, t].T @ dz
            dWh += h_prev.T @ dz
            db += dz.sum(0)
            dh_next = dz @ self.p["Wh"].T
            dc_next = dc * f
        return {"Wx": dWx, "Wh": dWh, "b": db}


class GRUClassifier(_RNNBase):
    kind = "gru"
    gates = 3  # z, r, n

    def _init_extra(self):
        self.p["bhn"] = np.zeros(self.H)

    def _forward(self, X):
        B, T, _ = X.shape
        H = self.H
        h = np.zeros((B, H))
        hs = np.zeros((B, T, H))
        cache = []
        Wh = self.p["Wh"]
        for t in range(T):
            xz = X[:, t] @ self.p["Wx"] + self.p["b"]
            hu = h @ Wh
            z = _sig(xz[:, :H] + hu[:, :H])
            r = _sig(xz[:, H:2 * H] + hu[:, H:2 * H])
            hn = hu[:, 2 * H:] + self.p["bhn"]
            n = np.tanh(xz[:, 2 * H:] + r * hn)
            h_prev = h
            h = (1 - z) * n + z * h_prev
            hs[:, t] = h
            cache.append((z, r, n, hn, h_prev))
        return hs, cache

    def _backward(self, X, dhs, cache):
        B, T, _ = X.shape
        H = self.H
        g = {k: np.zeros_like(self.p[k]) for k in ("Wx", "Wh", "b", "bhn")}
        dh_next = np.zeros((B, H))
        Wh = self.p["Wh"]
        for t in reversed(range(T)):
            z, r, n, hn, h_prev = cache[t]
            dh = dhs[:, t] + dh_next
            dn = dh * (1 - z)
            dzz = dh * (h_prev - n)
            dn_pre = dn * (1 - n**2)
            dr_pre = dn_pre * hn * r * (1 - r)
            dz_pre = dzz * z * (1 - z)
            dx_all = np.concatenate([dz_pre, dr_pre, dn_pre], axis=1)
            dh_all = np.concatenate([dz_pre, dr_pre, dn_pre * r], axis=1)
            g["Wx"] += X[:, t].T @ dx_all
            g["b"] += dx_all.sum(0)
            g["Wh"] += h_prev.T @ dh_all
            g["bhn"] += (dn_pre * r).sum(0)
            dh_next = dh * z + dh_all @ Wh.T
        return g


def pooled_stats(X: np.ndarray) -> np.ndarray:
    return np.concatenate([X.mean(1), X.std(1), X.max(1) - X.min(1)], axis=1)


class PooledLogReg:
    kind = "pooled_logreg"

    def __init__(self, n_features: int, n_classes: int, C_reg: float = 1.0, seed: int = 0):
        self.D, self.C, self.C_reg, self.seed = n_features, n_classes, C_reg, seed
        self.W = np.zeros((3 * n_features, n_classes))
        self.b = np.zeros(n_classes)
        self.mu = np.zeros(3 * n_features)
        self.sd = np.ones(3 * n_features)
        self.temperature = 1.0

    def fit(self, X, y, sample_weight=None):
        from sklearn.linear_model import LogisticRegression

        F = pooled_stats(X)
        self.mu, self.sd = F.mean(0), np.maximum(F.std(0), 1e-3)
        clf = LogisticRegression(C=self.C_reg, max_iter=2000, random_state=self.seed)
        clf.fit((F - self.mu) / self.sd, y, sample_weight=sample_weight)
        self.W = np.zeros((F.shape[1], self.C))
        self.b = np.full(self.C, -30.0)  # classes absent from training get ~0 probability
        coef, inter = clf.coef_, clf.intercept_
        if len(clf.classes_) == 2 and coef.shape[0] == 1:
            coef = np.vstack([-coef[0] / 2, coef[0] / 2])
            inter = np.array([-inter[0] / 2, inter[0] / 2])
        for row, cls in enumerate(clf.classes_):
            self.W[:, cls] = coef[row]
            self.b[cls] = inter[row]
        return self

    def logits(self, X):
        return (((pooled_stats(X) - self.mu) / self.sd) @ self.W + self.b) / self.temperature

    def predict_proba(self, X):
        return softmax(self.logits(X))

    def meta(self):
        return {"kind": self.kind, "D": self.D, "C": self.C, "C_reg": self.C_reg,
                "seed": self.seed, "temperature": self.temperature}

    def save(self, path: Path):
        np.savez(path, W=self.W, b=self.b, mu=self.mu, sd=self.sd)

    @classmethod
    def from_saved(cls, meta, path):
        m = cls(meta["D"], meta["C"], meta.get("C_reg", 1.0), meta.get("seed", 0))
        with np.load(path, allow_pickle=False) as z:
            m.W, m.b, m.mu, m.sd = z["W"], z["b"], z["mu"], z["sd"]
        m.temperature = float(meta.get("temperature", 1.0))
        return m


def dtw_distance(a: np.ndarray, b: np.ndarray, window: int | None = None) -> float:
    Ta, Tb = len(a), len(b)
    cost = np.sqrt(((a[:, None, :] - b[None, :, :]) ** 2).sum(-1))
    D = np.full((Ta + 1, Tb + 1), np.inf)
    D[0, 0] = 0.0
    w = max(window or max(Ta, Tb), abs(Ta - Tb))
    for i in range(1, Ta + 1):
        for j in range(max(1, i - w), min(Tb, i + w) + 1):
            D[i, j] = cost[i - 1, j - 1] + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
    return float(D[Ta, Tb] / (Ta + Tb))


class DTW1NN:
    """Reference method; scores are -min-distance per class (not probabilities)."""

    kind = "dtw_1nn"

    def __init__(self, n_features: int, n_classes: int, window: int = 6, seed: int = 0):
        self.D, self.C, self.window, self.seed = n_features, n_classes, window, seed
        self.norm = Normalizer()
        self.X = np.zeros((0, 1, n_features))
        self.y = np.zeros(0, dtype=int)
        self.temperature = 1.0
        self.scale = 1.0

    def fit(self, X, y, sample_weight=None):
        self.norm.fit(X)
        self.X, self.y = self.norm(X), np.asarray(y)
        return self

    def logits(self, X):
        Xn = self.norm(X)
        out = np.full((len(Xn), self.C), -1e3)
        for n, q in enumerate(Xn):
            d = np.array([dtw_distance(q, r, self.window) for r in self.X])
            for c in np.unique(self.y):
                out[n, c] = -d[self.y == c].min() / self.scale
        return out / self.temperature

    def predict_proba(self, X):
        return softmax(self.logits(X))

    def meta(self):
        return {"kind": self.kind, "D": self.D, "C": self.C, "window": self.window,
                "seed": self.seed, "temperature": self.temperature, "scale": self.scale}

    def save(self, path):
        np.savez(path, X=self.X, y=self.y, norm_mean=self.norm.mean, norm_std=self.norm.std)

    @classmethod
    def from_saved(cls, meta, path):
        m = cls(meta["D"], meta["C"], meta.get("window", 6), meta.get("seed", 0))
        with np.load(path, allow_pickle=False) as z:
            m.X, m.y = z["X"], z["y"]
            m.norm = Normalizer(z["norm_mean"], z["norm_std"])
        m.temperature = float(meta.get("temperature", 1.0))
        m.scale = float(meta.get("scale", 1.0))
        return m


REGISTRY = {c.kind: c for c in (LSTMClassifier, GRUClassifier, PooledLogReg, DTW1NN)}


def save_model(model, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    model.save(directory / "weights.npz")
    (directory / "architecture.json").write_text(json.dumps(model.meta(), indent=2))


def load_model(directory: Path):
    meta = json.loads((directory / "architecture.json").read_text())
    cls = REGISTRY.get(meta["kind"])
    if cls is None:
        raise ValueError(f"unknown model kind {meta['kind']!r}")
    return cls.from_saved(meta, directory / "weights.npz")


def fit_temperature(logits: np.ndarray, y: np.ndarray) -> float:
    """Temperature scaling on held-out validation logits (minimise NLL)."""
    best_t, best = 1.0, np.inf
    for t in np.exp(np.linspace(np.log(0.05), np.log(20), 120)):
        p = softmax(logits / t)
        nll = -np.mean(np.log(p[np.arange(len(y)), y] + 1e-12))
        if nll < best:
            best, best_t = nll, float(t)
    return best_t
