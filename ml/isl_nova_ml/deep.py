"""Additional sequence classifiers in NumPy (forward + hand-written backward).

* ``TCNClassifier``          - dilated temporal convolutions (k=3, dilations 1/2/4) with residuals,
                               mean + max pooled.
* ``TransformerClassifier``  - 2-layer pre-LayerNorm Transformer encoder (4 heads), learned positions,
                               mean pooled.
* ``BiLSTMAttnClassifier``   - bidirectional LSTM with additive attention pooling.
* ``EnsembleModel``          - average of calibrated member probabilities (one weights file).

All share the training API of ``models._RNNBase`` (``p`` dict, ``loss_and_grads``,
``train_epoch``, Adam, ``Normalizer``, temperature). Every backward pass is checked
against numerical gradients in ``ml/tests/test_deep.py``. No pickle, no autodiff
framework: the same code runs in the training workflow and in the API.
"""

from __future__ import annotations

import numpy as np

from . import models as _models
from .models import Normalizer, _RNNBase, _sig, softmax

# --------------------------------------------------------------------------- helpers

def _ln_fwd(x, g, b, eps=1e-5):
    mu = x.mean(-1, keepdims=True)
    var = x.var(-1, keepdims=True)
    inv = 1.0 / np.sqrt(var + eps)
    xh = (x - mu) * inv
    return xh * g + b, (xh, inv)


def _ln_bwd(dy, g, cache):
    xh, inv = cache
    dg = (dy * xh).reshape(-1, xh.shape[-1]).sum(0)
    db = dy.reshape(-1, xh.shape[-1]).sum(0)
    dxh = dy * g
    n = xh.shape[-1]
    dx = inv / n * (n * dxh - dxh.sum(-1, keepdims=True) - xh * (dxh * xh).sum(-1, keepdims=True))
    return dx, dg, db


def _xent(logits, y, w):
    P = softmax(logits)
    B = len(y)
    wn = w / w.sum()
    loss = float(-(wn * np.log(P[np.arange(B), y] + 1e-12)).sum())
    dl = P.copy()
    dl[np.arange(B), y] -= 1.0
    return loss, dl * wn[:, None]


class _DeepBase(_RNNBase):
    """Shared plumbing; subclasses define _init_params, _forward_logits, _backward."""

    kind = "deep"

    def __init__(self, n_features: int, n_classes: int, hidden: int = 64, seed: int = 0):
        self.D, self.C, self.H, self.seed = n_features, n_classes, hidden, seed
        self.rng = np.random.default_rng(seed)
        self.p: dict[str, np.ndarray] = {}
        self._init_params()
        self.norm = Normalizer()
        self.temperature = 1.0

    def _w(self, *shape, fan_in=None):
        fan_in = fan_in or shape[0]
        return self.rng.normal(0, np.sqrt(2.0 / (fan_in + shape[-1])), shape)

    def logits_raw(self, Xn):
        out = []
        for s in range(0, len(Xn), 256):  # bounded memory at inference
            out.append(self._forward_logits(Xn[s: s + 256])[0])
        return np.concatenate(out) if out else np.zeros((0, self.C))

    def loss_and_grads(self, Xn, y, w):
        logits, cache = self._forward_logits(Xn)
        loss, dl = _xent(logits, y, w)
        return loss, self._backward(dl, cache)


# --------------------------------------------------------------------------- TCN

class TCNClassifier(_DeepBase):
    kind = "tcn"
    DILATIONS = (1, 2, 4)

    def _init_params(self):
        D, H, C = self.D, self.H, self.C
        self.p["Win"], self.p["bin"] = self._w(D, H), np.zeros(H)
        for i, _ in enumerate(self.DILATIONS):
            self.p[f"Wc{i}"] = self._w(3 * H, H, fan_in=3 * H)
            self.p[f"bc{i}"] = np.zeros(H)
        self.p["Whead"], self.p["bhead"] = self._w(2 * H, C), np.zeros(C)

    @staticmethod
    def _shift(x, s):
        """out[:, t] = x[:, t + s] (zero outside)."""
        out = np.zeros_like(x)
        T = x.shape[1]
        if s > 0:
            out[:, : T - s] = x[:, s:]
        elif s < 0:
            out[:, -s:] = x[:, : T + s]
        else:
            out[:] = x
        return out

    def _forward_logits(self, X):
        h = X @ self.p["Win"] + self.p["bin"]
        caches = []
        for i, d in enumerate(self.DILATIONS):
            xc = np.concatenate([self._shift(h, -d), h, self._shift(h, d)], axis=-1)
            z = xc @ self.p[f"Wc{i}"] + self.p[f"bc{i}"]
            a = np.maximum(z, 0)
            caches.append((xc, z))
            h = h + a
        mx_idx = h.argmax(1)
        pooled = np.concatenate([h.mean(1), h.max(1)], axis=1)
        logits = pooled @ self.p["Whead"] + self.p["bhead"]
        return logits, (X, caches, h, mx_idx, pooled)

    def _backward(self, dl, cache):
        X, caches, h, mx_idx, pooled = cache
        B, T, H = h.shape
        g = {"Whead": pooled.T @ dl, "bhead": dl.sum(0)}
        dp = dl @ self.p["Whead"].T
        dh = np.repeat((dp[:, :H] / T)[:, None, :], T, axis=1)
        bi = np.arange(B)[:, None]
        hi = np.arange(H)[None, :]
        np.add.at(dh, (bi, mx_idx, hi), dp[:, H:])
        for i in reversed(range(len(self.DILATIONS))):
            d = self.DILATIONS[i]
            xc, z = caches[i]
            dz = dh * (z > 0)
            g[f"Wc{i}"] = xc.reshape(-1, 3 * H).T @ dz.reshape(-1, H)
            g[f"bc{i}"] = dz.sum((0, 1))
            dxc = dz @ self.p[f"Wc{i}"].T
            # xc = [shift(h,-d), h, shift(h,d)]; shift(x,s)^T = shift(., -s)
            dh = dh + self._shift(dxc[..., :H], d) + dxc[..., H: 2 * H] + self._shift(dxc[..., 2 * H:], -d)
        g["Win"] = X.reshape(-1, X.shape[-1]).T @ dh.reshape(-1, H)
        g["bin"] = dh.sum((0, 1))
        return g


# --------------------------------------------------------------------------- Transformer

class TransformerClassifier(_DeepBase):
    kind = "transformer"
    LAYERS = 2
    HEADS = 4
    T_MAX = 64

    def _init_params(self):
        D, H, C = self.D, self.H, self.C
        p = self.p
        p["Win"], p["bin"] = self._w(D, H), np.zeros(H)
        p["pos"] = self.rng.normal(0, 0.02, (self.T_MAX, H))
        for i in range(self.LAYERS):
            p[f"g1_{i}"], p[f"b1_{i}"] = np.ones(H), np.zeros(H)
            for n in ("q", "k", "v", "o"):
                p[f"W{n}{i}"] = self._w(H, H)
                p[f"b{n}{i}"] = np.zeros(H)
            p[f"g2_{i}"], p[f"b2_{i}"] = np.ones(H), np.zeros(H)
            p[f"Wf1{i}"], p[f"bf1{i}"] = self._w(H, 2 * H), np.zeros(2 * H)
            p[f"Wf2{i}"], p[f"bf2{i}"] = self._w(2 * H, H), np.zeros(H)
        p["gf"], p["bf"] = np.ones(H), np.zeros(H)
        p["Whead"], p["bhead"] = self._w(H, C), np.zeros(C)

    def _split(self, x):
        B, T, H = x.shape
        return x.reshape(B, T, self.HEADS, H // self.HEADS).transpose(0, 2, 1, 3)

    def _merge(self, x):
        B, nh, T, dh = x.shape
        return x.transpose(0, 2, 1, 3).reshape(B, T, nh * dh)

    def _forward_logits(self, X):
        p = self.p
        B, T, _ = X.shape
        x = X @ p["Win"] + p["bin"] + p["pos"][:T]
        layers = []
        for i in range(self.LAYERS):
            h1, ln1 = _ln_fwd(x, p[f"g1_{i}"], p[f"b1_{i}"])
            q, k, v = (self._split(h1 @ p[f"W{n}{i}"] + p[f"b{n}{i}"]) for n in "qkv")
            dh = q.shape[-1]
            att = softmax(q @ k.transpose(0, 1, 3, 2) / np.sqrt(dh), axis=-1)
            o = self._merge(att @ v)
            x = x + o @ p[f"Wo{i}"] + p[f"bo{i}"]
            h2, ln2 = _ln_fwd(x, p[f"g2_{i}"], p[f"b2_{i}"])
            f_pre = h2 @ p[f"Wf1{i}"] + p[f"bf1{i}"]
            f = np.maximum(f_pre, 0)
            x = x + f @ p[f"Wf2{i}"] + p[f"bf2{i}"]
            layers.append((h1, ln1, q, k, v, att, o, h2, ln2, f_pre, f))
        hf, lnf = _ln_fwd(x, p["gf"], p["bf"])
        pooled = hf.mean(1)
        logits = pooled @ p["Whead"] + p["bhead"]
        return logits, (X, layers, lnf, pooled, T)

    def _backward(self, dl, cache):
        p = self.p
        X, layers, lnf, pooled, T = cache
        g = {"Whead": pooled.T @ dl, "bhead": dl.sum(0)}
        dpool = dl @ p["Whead"].T
        dhf = np.repeat((dpool / T)[:, None, :], T, axis=1)
        dx, g["gf"], g["bf"] = _ln_bwd(dhf, p["gf"], lnf)
        H = self.H
        for i in reversed(range(self.LAYERS)):
            h1, ln1, q, k, v, att, o, h2, ln2, f_pre, f = layers[i]
            # FFN
            g[f"Wf2{i}"] = f.reshape(-1, 2 * H).T @ dx.reshape(-1, H)
            g[f"bf2{i}"] = dx.sum((0, 1))
            df = (dx @ p[f"Wf2{i}"].T) * (f_pre > 0)
            g[f"Wf1{i}"] = h2.reshape(-1, H).T @ df.reshape(-1, 2 * H)
            g[f"bf1{i}"] = df.sum((0, 1))
            dh2 = df @ p[f"Wf1{i}"].T
            d, g[f"g2_{i}"], g[f"b2_{i}"] = _ln_bwd(dh2, p[f"g2_{i}"], ln2)
            dx = dx + d
            # attention
            g[f"Wo{i}"] = o.reshape(-1, H).T @ dx.reshape(-1, H)
            g[f"bo{i}"] = dx.sum((0, 1))
            do = self._split(dx @ p[f"Wo{i}"].T)
            dhd = q.shape[-1]
            datt = do @ v.transpose(0, 1, 3, 2)
            dv = att.transpose(0, 1, 3, 2) @ do
            ds = att * (datt - (datt * att).sum(-1, keepdims=True)) / np.sqrt(dhd)
            dq = ds @ k
            dk = ds.transpose(0, 1, 3, 2) @ q
            dh1 = np.zeros_like(h1)
            for n, dn in (("q", dq), ("k", dk), ("v", dv)):
                dm = self._merge(dn)
                g[f"W{n}{i}"] = h1.reshape(-1, H).T @ dm.reshape(-1, H)
                g[f"b{n}{i}"] = dm.sum((0, 1))
                dh1 += dm @ p[f"W{n}{i}"].T
            d, g[f"g1_{i}"], g[f"b1_{i}"] = _ln_bwd(dh1, p[f"g1_{i}"], ln1)
            dx = dx + d
        dpos = np.zeros_like(p["pos"])
        dpos[:T] = dx.sum(0)
        g["pos"] = dpos
        g["Win"] = X.reshape(-1, X.shape[-1]).T @ dx.reshape(-1, H)
        g["bin"] = dx.sum((0, 1))
        return g


# --------------------------------------------------------------------------- BiLSTM + attention

def _lstm_fwd(X, Wx, Wh, b, H):
    B, T, _ = X.shape
    h = np.zeros((B, H))
    c = np.zeros((B, H))
    hs = np.zeros((B, T, H))
    cache = []
    for t in range(T):
        z = X[:, t] @ Wx + h @ Wh + b
        i, f, o = _sig(z[:, :H]), _sig(z[:, H:2 * H]), _sig(z[:, 2 * H:3 * H])
        gg = np.tanh(z[:, 3 * H:])
        c_prev, h_prev = c, h
        c = f * c + i * gg
        tc = np.tanh(c)
        h = o * tc
        hs[:, t] = h
        cache.append((i, f, o, gg, c_prev, h_prev, tc))
    return hs, cache


def _lstm_bwd(X, dhs, cache, Wx, Wh, H):
    B, T, _ = X.shape
    dWx, dWh, db = np.zeros_like(Wx), np.zeros_like(Wh), np.zeros(Wx.shape[1])
    dX = np.zeros_like(X)
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
        dX[:, t] = dz @ Wx.T
        dh_next = dz @ Wh.T
        dc_next = dc * f
    return dWx, dWh, db, dX


class BiLSTMAttnClassifier(_DeepBase):
    kind = "bilstm_attn"
    ATT = 64

    def _init_params(self):
        D, H, C, A = self.D, self.H, self.C, self.ATT
        s_in, s_h = 1.0 / np.sqrt(D), 1.0 / np.sqrt(H)
        for d in ("f", "r"):
            self.p[f"W{d}x"] = self.rng.uniform(-s_in, s_in, (D, 4 * H))
            self.p[f"W{d}h"] = self.rng.uniform(-s_h, s_h, (H, 4 * H))
            b = np.zeros(4 * H)
            b[H: 2 * H] = 1.0
            self.p[f"b{d}"] = b
        self.p["Watt"], self.p["batt"] = self._w(2 * H, A), np.zeros(A)
        self.p["vatt"] = self.rng.normal(0, 1.0 / np.sqrt(A), A)
        self.p["Whead"], self.p["bhead"] = self._w(4 * H, C), np.zeros(C)

    def _forward_logits(self, X):
        p, H = self.p, self.H
        hf, cf = _lstm_fwd(X, p["Wfx"], p["Wfh"], p["bf"], H)
        hr_rev, cr = _lstm_fwd(X[:, ::-1], p["Wrx"], p["Wrh"], p["br"], H)
        hs = np.concatenate([hf, hr_rev[:, ::-1]], axis=-1)
        u = np.tanh(hs @ p["Watt"] + p["batt"])
        e = u @ p["vatt"]
        a = softmax(e, axis=1)
        ctx = (a[..., None] * hs).sum(1)
        pooled = np.concatenate([ctx, hs.mean(1)], axis=1)
        logits = pooled @ p["Whead"] + p["bhead"]
        return logits, (X, cf, cr, hs, u, a, pooled)

    def _backward(self, dl, cache):
        p, H = self.p, self.H
        X, cf, cr, hs, u, a, pooled = cache
        B, T, H2 = hs.shape
        g = {"Whead": pooled.T @ dl, "bhead": dl.sum(0)}
        dp = dl @ p["Whead"].T
        dctx, dmean = dp[:, :H2], dp[:, H2:]
        dhs = np.repeat((dmean / T)[:, None, :], T, axis=1) + a[..., None] * dctx[:, None, :]
        da = (hs * dctx[:, None, :]).sum(-1)
        de = a * (da - (da * a).sum(1, keepdims=True))
        g["vatt"] = (u * de[..., None]).sum((0, 1))
        du = de[..., None] * p["vatt"] * (1 - u**2)
        g["Watt"] = hs.reshape(-1, H2).T @ du.reshape(-1, du.shape[-1])
        g["batt"] = du.sum((0, 1))
        dhs = dhs + du @ p["Watt"].T
        g["Wfx"], g["Wfh"], g["bf"], _ = _lstm_bwd(X, dhs[..., :H], cf, p["Wfx"], p["Wfh"], H)
        g["Wrx"], g["Wrh"], g["br"], _ = _lstm_bwd(X[:, ::-1], dhs[:, ::-1, H:], cr, p["Wrx"], p["Wrh"], H)
        return g


# --------------------------------------------------------------------------- ensemble

class EnsembleModel:
    """Average of the members' calibrated probabilities, re-calibrated by one temperature."""

    kind = "ensemble"

    def __init__(self, members: list):
        self.members = members
        self.D, self.C = members[0].D, members[0].C
        self.temperature = 1.0

    def logits(self, X):
        P = np.mean([m.predict_proba(X) for m in self.members], axis=0)
        return np.log(np.clip(P, 1e-12, 1.0)) / self.temperature

    def predict_proba(self, X):
        return softmax(self.logits(X))

    def meta(self) -> dict:
        return {"kind": "ensemble", "D": self.D, "C": self.C, "temperature": self.temperature,
                "members": [m.meta() for m in self.members]}

    def save(self, path) -> None:
        arrays = {}
        for i, m in enumerate(self.members):
            for k, v in m.p.items():
                arrays[f"m{i}__{k}"] = v
            arrays[f"m{i}__norm_mean"] = m.norm.mean
            arrays[f"m{i}__norm_std"] = m.norm.std
        np.savez(path, **arrays)

    @classmethod
    def from_saved(cls, meta: dict, path):
        from .models import REGISTRY
        members = []
        with np.load(path, allow_pickle=False) as z:
            for i, mm in enumerate(meta["members"]):
                mc = REGISTRY[mm["kind"]]
                m = mc(mm["D"], mm["C"], mm["H"], mm.get("seed", 0))
                for k in m.p:
                    m.p[k] = z[f"m{i}__{k}"].astype(np.float64)
                m.norm = Normalizer(z[f"m{i}__norm_mean"], z[f"m{i}__norm_std"])
                m.temperature = float(mm.get("temperature", 1.0))
                members.append(m)
        e = cls(members)
        e.temperature = float(meta.get("temperature", 1.0))
        return e


_models.REGISTRY.update({c.kind: c for c in (TCNClassifier, TransformerClassifier, BiLSTMAttnClassifier, EnsembleModel)})
