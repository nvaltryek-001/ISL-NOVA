"""Evaluation metrics computed on held-out data only."""

from __future__ import annotations

import numpy as np


def topk_accuracy(P: np.ndarray, y: np.ndarray, k: int) -> float:
    if len(y) == 0:
        return float("nan")
    k = min(k, P.shape[1])
    top = np.argsort(-P, axis=1)[:, :k]
    return float(np.mean([y[i] in top[i] for i in range(len(y))]))


def confusion(y: np.ndarray, pred: np.ndarray, n: int) -> np.ndarray:
    M = np.zeros((n, n), dtype=int)
    for a, b in zip(y, pred, strict=True):
        M[a, b] += 1
    return M


def per_class(M: np.ndarray) -> list[dict]:
    out = []
    for c in range(M.shape[0]):
        tp = M[c, c]
        support = int(M[c].sum())
        pp = int(M[:, c].sum())
        p = tp / pp if pp else 0.0
        r = tp / support if support else 0.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        out.append({"class": c, "precision": p, "recall": r, "f1": f, "support": support})
    return out


def expected_calibration_error(P: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    if len(y) == 0:
        return float("nan")
    conf = P.max(1)
    correct = (P.argmax(1) == y).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            ece += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(ece)


def auroc(pos: np.ndarray, neg: np.ndarray) -> float:
    """P(score_pos > score_neg) with ties counted half (Mann-Whitney U)."""
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    s = np.concatenate([pos, neg])
    order = s.argsort()
    ranks = np.empty(len(s))
    ranks[order] = np.arange(1, len(s) + 1)
    # average ties
    for v in np.unique(s):
        idx = s == v
        ranks[idx] = ranks[idx].mean()
    u = ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2
    return float(u / (len(pos) * len(neg)))


def classification_report(P: np.ndarray, y: np.ndarray, n_classes: int) -> dict:
    pred = P.argmax(1) if len(y) else np.zeros(0, int)
    M = confusion(y, pred, n_classes)
    pc = per_class(M)
    present = [d for d in pc if d["support"] > 0]
    total = sum(d["support"] for d in present)
    return {
        "n": int(len(y)),
        "top1": topk_accuracy(P, y, 1),
        "top5": topk_accuracy(P, y, 5),
        "macro_f1": float(np.mean([d["f1"] for d in present])) if present else float("nan"),
        "weighted_f1": float(sum(d["f1"] * d["support"] for d in present) / total) if total else float("nan"),
        "ece": expected_calibration_error(P, y),
        "per_class": pc,
        "confusion": M.tolist(),
    }


def open_set_report(P_known: np.ndarray, P_unknown: np.ndarray, tau: float) -> dict:
    ck, cu = P_known.max(1), P_unknown.max(1) if len(P_unknown) else np.zeros(0)
    return {
        "tau": tau,
        "known_accept_rate": float(np.mean(ck >= tau)) if len(ck) else float("nan"),
        "unknown_reject_rate": float(np.mean(cu < tau)) if len(cu) else float("nan"),
        "auroc_maxprob": auroc(ck, cu),
        "n_unknown": int(len(cu)),
    }


def choose_threshold(P_val: np.ndarray, y_val: np.ndarray, keep: float = 0.95) -> float:
    """Confidence threshold that keeps ``keep`` of correct validation predictions."""
    if len(y_val) == 0:
        return 0.5
    ok = P_val.argmax(1) == y_val
    conf = P_val.max(1)[ok]
    if len(conf) == 0:
        return float(np.quantile(P_val.max(1), 0.5))
    return float(np.quantile(conf, 1 - keep))
