"""Inference with explicit prediction states.

States: recognized | uncertain | unknown | insufficient_input | model_unavailable.
(camera_unavailable is a client-side state.)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from . import contract as C
from .features import extract_features
from .models import load_model
from .openset import OTHER_ID, detector_features, detector_score
from .registry import Registry, RegistryError, verify_integrity


class ModelUnavailable(RuntimeError):
    pass


class Predictor:
    def __init__(self, model_dir: Path):
        self.dir = Path(model_dir)
        self.info = json.loads((self.dir / "model.json").read_text())
        self.contract_version = self.info["contract"]["version"]
        if self.contract_version not in C.SUPPORTED:
            raise ModelUnavailable(
                f"model contract {self.contract_version} is not supported by this runtime ({sorted(C.SUPPORTED)})"
            )
        verify_integrity(self.dir)
        self.model = load_model(self.dir)
        self.classes = self.info["classes"]  # every model output, incl. an optional "__other__" class
        self.other_col = next((i for i, c in enumerate(self.classes) if c["sign_id"] == OTHER_ID), None)
        self.known_cols = [i for i, c in enumerate(self.classes) if c["sign_id"] != OTHER_ID]
        self.vocabulary = [self.classes[i] for i in self.known_cols]
        self.detector = self.info.get("open_set_detector")
        th = self.info.get("thresholds", {})
        self.tau = float(th.get("tau", 0.5))
        self.margin = float(th.get("margin", 0.1))
        self.synthetic = bool(self.info.get("synthetic"))

    @classmethod
    def from_registry(cls, root: Path) -> Predictor:
        reg = Registry(root)
        d = reg.active_dir()
        if d is None or not (d / "model.json").exists():
            raise ModelUnavailable("no active model in registry")
        try:
            return cls(d)
        except (RegistryError, FileNotFoundError, KeyError, ValueError) as exc:
            raise ModelUnavailable(str(exc)) from exc

    @property
    def needs_face(self) -> bool:
        return self.contract_version == C.CONTRACT_V2_VERSION

    def features(self, frames: list[dict], aspect: float = 1.0):
        """Feature tensor in this model's contract (1.0.0, or 2.0.0 with the face block)."""
        return extract_features(frames, aspect, self.contract_version)

    def predict_features(self, feats: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(feats[None].astype(np.float64))[0]

    def predict(self, frames: list[dict], aspect: float = 1.0, top_k: int = 5) -> dict:
        t0 = time.perf_counter()
        fr = self.features(frames, aspect)
        quality = {"raw_frames": fr.raw_frames, "hand_frame_ratio": round(fr.hand_frame_ratio, 3),
                   "pose_frame_ratio": round(fr.pose_frame_ratio, 3)}
        if fr.status != "ok":
            return {"state": "insufficient_input", "top": [], "reasons": fr.reasons, "quality": quality,
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 2), **self.describe()}
        p = self.predict_features(fr.features)
        return self.decide(p, top_k, quality, t0)

    def known_max(self, p: np.ndarray) -> float:
        return float(p[self.known_cols].max())

    def decide(self, p: np.ndarray, top_k: int, quality: dict, t0: float) -> dict:
        state, reasons = self.state_for(p)
        kc = np.asarray(self.known_cols)
        order = kc[np.argsort(-p[kc])[:top_k]]
        top = [{"sign_id": self.classes[i]["sign_id"], "label": self.classes[i]["label"],
                "probability": round(float(p[i]), 4)} for i in order]
        out = {"state": state, "top": top, "reasons": reasons, "quality": quality,
               "latency_ms": round((time.perf_counter() - t0) * 1000, 2), **self.describe()}
        if self.other_col is not None:
            out["other_probability"] = round(float(p[self.other_col]), 4)
        return out

    def state_for(self, p: np.ndarray) -> tuple[str, list[str]]:
        """recognized / uncertain / unknown for one calibrated probability vector."""
        if self.other_col is not None and int(np.argmax(p)) == self.other_col:
            return "unknown", [f"closest to signs outside the vocabulary (p={float(p[self.other_col]):.2f})"]
        K = np.sort(p[self.known_cols])[::-1]
        p1, p2 = float(K[0]), float(K[1]) if len(K) > 1 else 0.0
        if self.detector:
            s = float(detector_score(self.detector, detector_features(p[None], self.known_cols, self.other_col))[0])
            if s >= self.detector["t_recognized"]:
                return "recognized", []
            if s >= self.detector["t_uncertain"]:
                return "uncertain", [f"unknown-sign detector score {s:.2f} below {self.detector['t_recognized']:.2f}"]
            return "unknown", [f"unknown-sign detector score {s:.2f}: likely a sign outside the vocabulary"]
        if p1 >= self.tau and (p1 - p2) >= self.margin:
            return "recognized", []
        if p1 >= 0.6 * self.tau:
            return "uncertain", [f"top probability {p1:.2f} or margin {p1 - p2:.2f} below threshold"]
        return "unknown", [f"top probability {p1:.2f} below rejection threshold {0.6 * self.tau:.2f}"]

    def describe(self) -> dict:
        return {"model_id": self.info["model_id"], "synthetic": self.synthetic,
                "contract": self.info["contract"]["name"], "needs_face": self.needs_face,
                "decision_rule": "open_set_detector" if self.detector else "max_probability"}


class StreamSmoother:
    """Exponential moving average over successive window probabilities."""

    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha
        self.state: np.ndarray | None = None

    def update(self, p: np.ndarray | None) -> np.ndarray | None:
        if p is None:
            self.state = None
            return None
        self.state = p if self.state is None else self.alpha * p + (1 - self.alpha) * self.state
        return self.state
