# v3 models: new architectures, "__other__" class, ensembles and a production unknown-sign detector

**Run:** GitHub Actions [42851786127](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42851786127)
(`.github/workflows/include-v3.yml`, settings `ml/runs/include-v3.json`). Data: INCLUDE landmarks
from data run 41773683352 (the 200 vocabulary classes + 62 out-of-vocabulary glosses), official
train / val / test split. **Not signer-independent** (INCLUDE has no signer IDs).

## Method

* **New architectures** (NumPy, hand-written backward passes checked against numerical gradients in
  `ml/tests/test_deep.py`): dilated **TCN**, 2-layer **Transformer** encoder (4 heads), **BiLSTM with
  attention pooling**. All use the v2 frame-rate / crop / missed-detection augmentation (4 variants
  per training sequence). Three seeds each.
* **`__other__` class**: LSTM and Transformer variants trained with an extra class made of
  out-of-vocabulary recordings from gloss part **A1**.
* **Ensembles**: mean of calibrated member probabilities; members chosen by validation macro-F1
  (best per architecture, top-3, top-5), temperature and threshold re-fitted on validation.
* **Selection**: highest **validation** macro-F1 among all 21 models (singles + ensembles + the released
  v2 LSTM). The test split was evaluated once per model and never used to choose.
* **Unknown-sign detector**: logistic combination of max-probability, margin and entropy, fitted on
  known **validation** + unknown part **A2**; threshold chosen on that fit set (largest known-keep
  with fit FAR < 10 %). Evaluated **once** on known **test** + unknown part **B**. Parts A1, A2 and B
  have disjoint glosses (16 / 16 / 31 glosses by hash).

## Results on the held-out test split (635 sequences)

| Model (best seed by validation) | Val macro-F1 | Test top-1 | Test top-5 | Test macro-F1 | ECE | Size |
|---|---:|---:|---:|---:|---:|---:|
| **BiLSTM-attention s7 — selected** | **98.1 %** | **95.1 %** | **99.4 %** | 94.1 % | 0.013 | 2.57 MB |
| Ensemble (4 models, best per architecture) | 98.1 % | 96.9 % | 99.2 % | 96.8 % | 0.020 | 7.73 MB |
| Ensemble with `__other__` (3 models) | 98.1 % | 97.2 % | 99.1 % | 97.4 % | 0.032 | 4.93 MB |
| Transformer s7 | 97.4 % | 95.9 % | 98.9 % | 96.0 % | 0.027 | 1.57 MB |
| TCN s13 | 97.0 % | 96.5 % | 99.4 % | 96.5 % | 0.017 | 1.81 MB |
| LSTM + fps aug s13 | 96.1 % | 94.8 % | 98.7 % | 95.1 % | 0.025 | 1.78 MB |
| v2 released LSTM s7 | 95.8 % | 92.0 % | 98.7 % | 91.6 % | 0.015 | 1.78 MB |

Three-seed spread (test top-1): Transformer 95.1–96.2 %, TCN 95.6–96.5 %, BiLSTM-attention
94.2–95.1 %, LSTM + fps 93.7–94.8 %. Full table: `comparison.md` on the
[model release](https://github.com/nvaltryek-001/ISL-NOVA/releases/tag/model-bilstm_attn-20261110T162800Z-s7).

**Reading.** Validation macro-F1 tied at 98.1 % (271 validation sequences: one sequence ≈ 0.4
points) between the BiLSTM-attention model and two ensembles; the rule picked the single model.
The ensembles scored 1.8–2.1 points higher on test, but choosing them now *because* of the test
score would leak the test split into the selection, so the release stays with the validation
choice. With 1–4 test videos per class, differences of about 1 point are within noise.

## Unknown signs (part B: 31 glosses, 444 sequences never used for any choice)

| Decision rule, selected model | False acceptance (unknown shown as a sign) | False rejection (known not recognized) | Known recognized and correct |
|---|---:|---:|---:|
| Max probability (τ = 0.80) | 19.6 % | 8.0 % | 89.9 % |
| **Production detector (shipped)** | **8.8 %** | **13.2 %** | 85.2 % |

| | Target | Result |
|---|---|---|
| False acceptance | < 10 % | **8.8 % — met** |
| False rejection | ≤ 15 % | **13.2 % — met** |

AUROC: detector 0.954, max probability 0.949. For comparison, v1 shipped 29.3 % false
acceptance and v2 34.0 % (different evaluation set: all 62 glosses). Per-model part-B results:
`part_b.md` on the release.

The detector ships inside the model (`open_set_detector` in `model.json`) and is used by the
server **and** by the on-device (offline) runtime. Its states: recognized / uncertain / unknown.

## The `__other__` class

Training with an explicit `__other__` class did not beat the detector: on part B the `__other__`
LSTM models accepted 18.7 % and 25.0 % of unknown signs at their max-probability threshold, the
`__other__` Transformers 16.0 % and 19.6 %. It remains available (`other_class: true`).

## End to end

The selected model, loaded through the production `Predictor`, reproduced **95.1 % top-1 / 99.4 %
top-5** on all 635 test sequences (median 18 ms per request including feature extraction). The
TypeScript on-device runtime matches it to 1e-8 and agreed with the server on 24/24 held-out samples.

## Not shown by these numbers

New signers, a live person at a webcam, regional variation, lighting and camera differences.
