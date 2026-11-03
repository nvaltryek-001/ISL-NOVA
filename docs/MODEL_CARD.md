# Model card

## Status: **no production model exists**

No model has been trained on authentic ISL recordings in this repository, because no such data was available in the build environment (see [REPOSITORY_AUDIT.md](REPOSITORY_AUDIT.md)). The application reports `model_unavailable` everywhere a prediction would appear. **There are no accuracy figures to report.**

## Implemented model families

| Kind | Description | Role |
|---|---|---|
| `lstm` | 1-layer LSTM, concatenated last + mean hidden state → softmax; Adam, gradient clipping, weight decay, class weighting, early stopping on validation macro-F1, LR decay on plateau | **Baseline** |
| `gru` | Same head on a GRU | Comparison |
| `pooled_logreg` | mean/std/range over time → multinomial logistic regression | Non-temporal baseline |
| `dtw_1nn` | Dynamic time warping, 1-nearest neighbour (Sakoe-Chiba band) | Reference method |

All use the same feature contract and splits. The recurrent models' backward passes are verified against finite differences in `ml/tests/test_ml.py`.

**Calibration and rejection.** Temperature scaling is fitted on validation logits. The rejection threshold τ keeps 95 % of correct validation predictions, and a top-1/top-2 margin is also required. Predictions resolve to *recognized* (p ≥ τ and margin met), *uncertain* (p ≥ 0.6 τ) or *unknown*.

## How to produce the first real model

```bash
# 1. import INCLUDE (docs/DATASET_PROTOCOL.md), review, then approve
PYTHONPATH=ml python -m isl_nova_ml.include_import --include-root /data/INCLUDE --out data/processed/include \
    --hand-model models/hand_landmarker.task --pose-model models/pose_landmarker_lite.task --approve
# 2. train the baseline (CPU; expect hours for 200 classes with the NumPy LSTM)
PYTHONPATH=ml python -m isl_nova_ml.train --config ml/configs/lstm_baseline.json \
    --manifest data/processed/include/manifest.json --data-root data/processed/include \
    --registry artifacts/models --dataset-version include-official-v1
# 3. inspect artifacts/models/<id>/metrics.json, then promote in the AI Laboratory (admin)
```

When a model is promoted, fill in the template below **from its `metrics.json`**.

| Field | Value |
|---|---|
| Model ID | _TBD_ |
| Training data / split | _TBD_ (INCLUDE official split: signer independence **unverified**) |
| Classes | _TBD_ |
| Test top-1 / top-5 / macro-F1 | _TBD_ |
| ECE (after temperature scaling) | _TBD_ |
| Unknown rejection (AUROC) | _TBD_ |
| Intended use | Isolated-sign recognition for practice and assistive look-up; **not** for interpretation in medical, legal or emergency settings |
| Known limitations | See [research/LIMITATIONS.md](../research/LIMITATIONS.md) |

## Synthetic smoke test (not a model of ISL)

`python -m isl_nova_ml.smoke` trains every model kind on procedurally generated trajectories, only to check that the code runs end to end. Those artefacts carry `synthetic: true`, use class IDs `SYN01…`, and are refused by the production registry. Their metrics must never be quoted.
