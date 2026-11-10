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


OTHER_ID = "__other__"
OTHER_LABEL = "Other (not in vocabulary)"


def gloss_half(gloss: str) -> str:
    return "A" if int(hashlib.sha256(gloss.encode()).hexdigest(), 16) % 2 == 0 else "B"


def unknown_part(gloss: str) -> str:
    """Disjoint gloss parts: half A split into A1 (train an __other__ class) and A2 (fit the detector);
    half B is evaluation only. B is identical to ``gloss_half(g) == "B"``."""
    h = int(hashlib.sha256(gloss.encode()).hexdigest(), 16)
    return "B" if h % 2 else ("A1" if h % 4 == 0 else "A2")


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


# --------------------------------------------------------------------------- production detector

def detector_features(P: np.ndarray, known_cols: list[int], other_col: int | None = None) -> dict[str, np.ndarray]:
    """Scores computed from calibrated probabilities only (no stored training statistics), so the
    Predictor can compute them for every request. Higher = more likely a vocabulary sign."""
    P = np.atleast_2d(P)
    K = P[:, known_cols]
    s = np.sort(K, 1)[:, ::-1]
    Kn = K / np.clip(K.sum(1, keepdims=True), 1e-12, None)
    feats = {"maxprob": s[:, 0], "margin": s[:, 0] - s[:, 1],
             "entropy": np.sum(Kn * np.log(np.clip(Kn, 1e-12, 1)), 1)}
    if other_col is not None:
        feats["other"] = -P[:, other_col]
    return feats


def fit_detector(known: dict[str, np.ndarray], unknown: dict[str, np.ndarray],
                 keeps=(0.95, 0.92, 0.90, 0.88, 0.85), target_far: float = 0.10, keep_uncertain: float = 0.98) -> dict:
    """Logistic combination fitted on (known validation, unknown part A2); thresholds chosen on the same
    fit set: the highest known-keep rate whose unknown acceptance is below ``target_far`` (else the lowest)."""
    from sklearn.linear_model import LogisticRegression

    names = list(known)
    Xk = np.c_[[known[n] for n in names]].T
    Xu = np.c_[[unknown[n] for n in names]].T
    X = np.r_[Xk, Xu]
    y = np.r_[np.ones(len(Xk)), np.zeros(len(Xu))]
    mu, sd = X.mean(0), X.std(0) + 1e-9
    lr = LogisticRegression(max_iter=5000, class_weight="balanced").fit((X - mu) / sd, y)
    det = {"kind": "logistic", "features": names, "mu": mu.tolist(), "sd": sd.tolist(),
           "coef": lr.coef_[0].tolist(), "intercept": float(lr.intercept_[0])}
    sk, su = detector_score(det, known), detector_score(det, unknown)
    chosen = None
    trials = []
    for keep in keeps:
        t = float(np.quantile(sk, 1 - keep))
        far = float((su >= t).mean())
        trials.append({"keep_known": keep, "threshold": t, "fit_far": far})
        if chosen is None and far < target_far:
            chosen = trials[-1]
    chosen = chosen or trials[-1]
    det.update({"t_recognized": chosen["threshold"], "t_uncertain": float(np.quantile(sk, 1 - keep_uncertain)),
                "chosen_on_fit_set": chosen, "fit_trials": trials,
                "fit_counts": {"known": int(len(sk)), "unknown": int(len(su))}})
    return det


def detector_score(det: dict, feats: dict[str, np.ndarray]) -> np.ndarray:
    X = np.c_[[np.asarray(feats[n], dtype=np.float64) for n in det["features"]]].T
    return ((X - np.asarray(det["mu"])) / np.asarray(det["sd"])) @ np.asarray(det["coef"]) + det["intercept"]
