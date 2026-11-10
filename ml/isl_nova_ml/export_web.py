"""Export a trained recurrent model for in-browser (offline) inference and to ONNX.

    python -m isl_nova_ml.export_web --model-dir artifacts/models/<id> --out web/   # model.json + weights.bin
    python -m isl_nova_ml.export_web --model-dir ... --onnx model.onnx              # needs `pip install onnx`

The web format is a small JSON header plus one little-endian float32 blob. The
TypeScript runtime in frontend/src/lib/webModel.ts implements the same forward
pass; frontend/tests/webModel.test.ts checks it against probabilities computed
here (fixture written by ``write_parity_fixture``).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .deep import BiLSTMAttnClassifier
from .models import GRUClassifier, LSTMClassifier, load_model

WEB_KINDS = ("lstm", "gru", "bilstm_attn")
WEB_FORMAT = "isl-nova-web-1"


def export_web(model_dir: Path, out_dir: Path) -> dict:
    model_dir, out_dir = Path(model_dir), Path(out_dir)
    info = json.loads((model_dir / "model.json").read_text())
    m = load_model(model_dir)
    if m.kind not in WEB_KINDS:
        raise ValueError(f"in-browser inference supports {WEB_KINDS}, not {m.kind!r}")
    arrays = {k: v for k, v in m.p.items()}
    arrays["norm_mean"], arrays["norm_std"] = m.norm.mean, m.norm.std
    layout, blobs, off = [], [], 0
    for k in sorted(arrays):
        a = np.ascontiguousarray(arrays[k], dtype="<f4")
        layout.append({"name": k, "shape": list(a.shape), "offset": off, "length": int(a.size)})
        blobs.append(a.tobytes())
        off += a.size
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "weights.bin").write_bytes(b"".join(blobs))
    th = info.get("thresholds", {})
    header = {"format": WEB_FORMAT, "model_id": info["model_id"], "kind": m.kind, "D": m.D, "C": m.C, "H": m.H,
              "temperature": m.temperature, "tau": th.get("tau", 0.5), "margin": th.get("margin", 0.1),
              "contract": info["contract"]["name"], "classes": info["classes"], "tensors": layout,
              "weights_bytes": off * 4, "synthetic": bool(info.get("synthetic")),
              "open_set_detector": info.get("open_set_detector")}
    (out_dir / "model.json").write_text(json.dumps(header))
    return header


def write_parity_fixture(path: Path, seed: int = 0) -> None:
    """Tiny random LSTM and GRU + inputs + reference probabilities for the TypeScript test."""
    rng = np.random.default_rng(seed)
    cases = []
    for cls in (LSTMClassifier, GRUClassifier, BiLSTMAttnClassifier):
        m = cls(6, 4, 5, seed)
        for k in m.p:
            m.p[k] = rng.normal(0, 0.5, m.p[k].shape)
        X = rng.normal(size=(3, 7, 6))
        m.norm.fit(X)
        m.temperature = 1.3
        cases.append({"kind": m.kind, "D": 6, "C": 4, "H": 5, "temperature": 1.3,
                      "params": {k: v.reshape(-1).tolist() for k, v in m.p.items()},
                      "shapes": {k: list(v.shape) for k, v in m.p.items()},
                      "norm_mean": m.norm.mean.tolist(), "norm_std": m.norm.std.tolist(),
                      "X": X.tolist(), "P": m.predict_proba(X).tolist()})
    Path(path).write_text(json.dumps({"format": WEB_FORMAT, "cases": cases}))


def export_onnx(model_dir: Path, path: Path) -> None:
    """LSTM -> ONNX (normalisation, LSTM op, last+mean pooling, linear head, temperature, softmax)."""
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    m = load_model(Path(model_dir))
    if m.kind != "lstm":
        raise ValueError("ONNX export is implemented for LSTM models")
    H, D, C = m.H, m.D, m.C
    Wx, Wh, b = m.p["Wx"], m.p["Wh"], m.p["b"]

    def reorder(a):  # ours: i, f, o, g  ->  ONNX: i, o, f, c
        i, f, o, g = (a[..., k * H:(k + 1) * H] for k in range(4))
        return np.concatenate([i, o, f, g], axis=-1)

    W = reorder(Wx).T[None].astype(np.float32)             # [1, 4H, D]
    R = reorder(Wh).T[None].astype(np.float32)             # [1, 4H, H]
    B = np.concatenate([reorder(b), np.zeros(4 * H)])[None].astype(np.float32)  # [1, 8H]
    inits = [numpy_helper.from_array(x, n) for x, n in (
        (m.norm.mean.astype(np.float32), "mean"), (m.norm.std.astype(np.float32), "std"), (W, "W"), (R, "R"), (B, "B"),
        (m.p["Wo"].astype(np.float32), "Wo"), (m.p["bo"].astype(np.float32), "bo"),
        (np.array(1.0 / m.temperature, np.float32), "invT"),
        (np.array([1, 0, 2], np.int64), "perm_unused"), (np.array([1], np.int64), "ax1"),
        (np.array([-1], np.int64), "last"), (np.array([2**31 - 1], np.int64), "end"))]
    nodes = [
        helper.make_node("Sub", ["x", "mean"], ["xc"]),
        helper.make_node("Div", ["xc", "std"], ["xn"]),
        helper.make_node("Transpose", ["xn"], ["xt"], perm=[1, 0, 2]),          # [T, N, D]
        helper.make_node("LSTM", ["xt", "W", "R", "B"], ["Y"], hidden_size=H),   # Y: [T, 1, N, H]
        helper.make_node("Squeeze", ["Y", "ax1"], ["Ys"]),                       # [T, N, H]
        helper.make_node("Slice", ["Ys", "last", "end"], ["Ylast"]),             # [1, N, H]
        helper.make_node("Squeeze", ["Ylast", "zero"], ["hlast"]),
        helper.make_node("ReduceMean", ["Ys"], ["hmean"], axes=[0], keepdims=0),
        helper.make_node("Concat", ["hlast", "hmean"], ["pooled"], axis=1),
        helper.make_node("MatMul", ["pooled", "Wo"], ["z0"]),
        helper.make_node("Add", ["z0", "bo"], ["z1"]),
        helper.make_node("Mul", ["z1", "invT"], ["z"]),
        helper.make_node("Softmax", ["z"], ["probabilities"], axis=1),
    ]
    inits.append(numpy_helper.from_array(np.array([0], np.int64), "zero"))
    g = helper.make_graph(nodes, "isl_nova_lstm",
                          [helper.make_tensor_value_info("x", TensorProto.FLOAT, ["N", "T", D])],
                          [helper.make_tensor_value_info("probabilities", TensorProto.FLOAT, ["N", C])], inits)
    model = helper.make_model(g, opset_imports=[helper.make_opsetid("", 17)], producer_name="isl-nova")
    onnx.checker.check_model(model)
    Path(path).write_bytes(model.SerializeToString())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-dir", type=Path)
    ap.add_argument("--out", type=Path, help="directory for model.json + weights.bin")
    ap.add_argument("--onnx", type=Path, help="write an ONNX file")
    ap.add_argument("--parity-fixture", type=Path, help="write the TypeScript parity fixture and exit")
    a = ap.parse_args(argv)
    if a.parity_fixture:
        write_parity_fixture(a.parity_fixture)
        return 0
    if a.out:
        h = export_web(a.model_dir, a.out)
        print(json.dumps({k: h[k] for k in ("model_id", "kind", "C", "weights_bytes")}))
    if a.onnx:
        export_onnx(a.model_dir, a.onnx)
        print(f"wrote {a.onnx}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
