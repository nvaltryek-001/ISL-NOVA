"""Unknown-sign (open-set) detectors compared on genuine data.

Protocol (no leakage):
  * fit set  = known VALIDATION sequences + unknown glosses in half A
  * eval set = known TEST sequences      + unknown glosses in half B (disjoint glosses)
Thresholds are chosen on the fit set only and then applied to the eval set.

Detectors (higher score = more likely a known sign):
  maxprob    calibrated max softmax probability (production baseline)
  margin     top-1 minus top-2 probability
  entropy    negative entropy of the calibrated distribution
  centroid   negative Mahalanobis distance of pooled features to the nearest
             class mean (shared Ledoit-Wolf covariance, fitted on TRAIN only)
  combined   logistic regression on the four scores above, fitted on the fit set
"""

from __future__ import annotations

import hashlib

import numpy as np

from .metrics import auroc

DETECTORS = ("maxprob", "margin", "entropy", "centroid", "combined")


def pooled(F: np.ndarray) -> np.ndarray:
    """Time-pooled statistics of a (T, D) feature sequence."""
    return np.concatenate([F.mean(0), F.std(0)])


def gloss_half(gloss: str) -> str:
    return "A" if int(hashlib.sha256(gloss.encode()).hexdigest(), 16) % 2 == 0 else "B"


class CentroidScorer:
    def fit(self, Z: np.ndarray, y: np.ndarray) -> CentroidScorer:
        from sklearn.covariance import LedoitWolf

        self.classes = np.unique(y)
        self.mu = np.stack([Z[y == c].mean(0) for c in self.classes])
        resid = Z - self.mu[np.searchsorted(self.classes, y)]
        self.P = LedoitWolf().fit(resid).precision_
        return self

    def score(self, Z: np.ndarray) -> np.ndarray:
        out = np.empty(len(Z))
        for i, z in enumerate(Z):
            d = self.mu - z
            out[i] = -np.min(np.einsum("cd,de,ce->c", d, self.P, d))
        return out


def base_scores(P: np.ndarray, cent: np.ndarray) -> dict[str, np.ndarray]:
    s = np.sort(P, 1)[:, ::-1]
    ent = -np.sum(P * np.log(np.clip(P, 1e-12, 1)), 1)
    return {"maxprob": s[:, 0], "margin": s[:, 0] - s[:, 1], "entropy": -ent, "centroid": cent}


def threshold_for(known: np.ndarray, keep: float) -> float:
    """Threshold that keeps `keep` of known sequences (accept if score >= thr)."""
    return float(np.quantile(known, 1 - keep))


def evaluate(fit: dict, ev: dict, keeps=(0.95, 0.90, 0.85)) -> dict:
    """fit/ev: {'known': {name: scores}, 'unknown': {name: scores}} -> per-detector report."""
    from sklearn.linear_model import LogisticRegression

    names = list(fit["known"])
    Xf = np.r_[np.c_[[fit["known"][n] for n in names]].T, np.c_[[fit["unknown"][n] for n in names]].T]
    yf = np.r_[np.ones(len(fit["known"][names[0]])), np.zeros(len(fit["unknown"][names[0]]))]
    mu, sd = Xf.mean(0), Xf.std(0) + 1e-9
    lr = LogisticRegression(max_iter=2000, class_weight="balanced").fit((Xf - mu) / sd, yf)

    def comb(d):
        X = np.c_[[d[n] for n in names]].T
        return lr.decision_function((X - mu) / sd)

    for part in (fit, ev):
        part["known"]["combined"] = comb(part["known"])
        part["unknown"]["combined"] = comb(part["unknown"])
    rep = {}
    for n in DETECTORS:
        k, u = ev["known"][n], ev["unknown"][n]
        row = {"auroc": float(auroc(k, u))}
        for keep in keeps:
            thr = threshold_for(fit["known"][n], keep)
            row[f"keep{int(keep * 100)}"] = {"threshold": thr, "false_rejection": float((k < thr).mean()),
                                             "false_acceptance": float((u >= thr).mean())}
        rep[n] = row
    return rep
