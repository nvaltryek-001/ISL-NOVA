# Model card: `bilstm_attn-20261110T162800Z-s7` (ISL NOVA v3, default)

| Field | Value |
|---|---|
| Model | Bidirectional LSTM (96 units per direction) with additive attention pooling + mean pooling → softmax over 200 signs; NumPy implementation with gradient-checked backward pass (`ml/isl_nova_ml/deep.py`) |
| Weights | [release `model-bilstm_attn-20261110T162800Z-s7`](https://github.com/nvaltryek-001/ISL-NOVA/releases/tag/model-bilstm_attn-20261110T162800Z-s7), tarball SHA-256 `584bbf6e3eaf4313d6edd02d7bfd1bf08cd2729ce5e9a174f61f95cfa92fd786`; 2.57 MB |
| Trained by | GitHub Actions run [42851786127](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42851786127), config `ml/configs/bilstm-attn_fps_aug.json`, seed 7, 671 s on a 4-vCPU runner |
| Training data | INCLUDE (Sridhar et al., ACM MM 2020, doi:10.1145/3394171.3413528), CC BY 4.0; official split 2,448 / 271 / 635; frame-rate / crop / missed-detection augmentation (4 variants per training sequence) |
| Selection | best **validation** macro-F1 among 21 candidates (98.1 %; exact tie with two ensembles, broken in favour of the smaller model) |
| Calibration | temperature 0.975; max-probability τ 0.80 (fallback rule) |
| Decision rule | **unknown-sign detector** stored in `model.json`: logistic on max-probability, margin and entropy, fitted on validation + out-of-vocabulary part A2; recognized ≥ 0.92, uncertain ≥ −2.46 |

## Held-out test results (635 sequences, evaluated once)

| Metric | v3 (this model) | v2 | v1 |
|---|---:|---:|---:|
| Top-1 accuracy | **95.1 %** | 92.0 % | 91.7 % |
| Top-5 accuracy | **99.4 %** | 98.7 % | 98.3 % |
| Macro precision / recall | 94.9 % / 95.0 % | 92.9 % / 92.6 % | 93.0 % / 92.4 % |
| Macro-F1 / weighted-F1 | **94.1 %** / 94.9 % | 91.6 % / 91.6 % | 91.7 % / 91.5 % |
| Expected calibration error | **0.013** | 0.015 | 0.027 |
| `Predictor` end-to-end, all 635 | 95.12 % top-1 (median 18 ms per request) | 91.97 % | 91.65 % |
| Decision states on test (detector) | 551 recognized · 61 uncertain · 23 unknown | | |

## Unknown signs (31 out-of-vocabulary glosses never used for any choice)

| Rule | False acceptance | False rejection | Known recognized and correct |
|---|---:|---:|---:|
| **Shipped detector** | **8.8 %** (target < 10 %: met) | **13.2 %** (target ≤ 15 %: met) | 85.2 % |
| Max probability alone | 19.6 % | 8.0 % | 89.9 % |

Details: [research/V3_MODELS.md](../research/V3_MODELS.md).

## On-device

The same model and detector run in the browser (`frontend/src/lib/webModel.ts`) for offline use;
probabilities match the server to 1e-8 and decisions agreed on 24/24 held-out samples.

## Browser pipeline (virtual camera)

[run 42859291767](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42859291767): 73 held-out INCLUDE clips played as the browser's webcam through the Live page (in-browser MediaPipe, CPU delegate, median 9 fps): **84.9 % top-1** (62/73; v2 83.6 %, v1 74.0 %), 95.9 % top-5; 50 recognized (**49 correct**), 15 uncertain, 8 unknown. Offline Python on the same clips: 93.2 %. The ≥ 85 % target is **not met** (one clip short). Not a live person.

## Intended use, limitations
As for earlier models: isolated signs only; **not signer-independent**; one school in Chennai;
no facial features (a face-feature model exists, see [V4_FACE_FEATURES.md](../research/V4_FACE_FEATURES.md), but is not the default); vocabulary and Hindi/Kannada meanings not linguist-verified; no live-person
or new-signer evaluation. **Not** for high-stakes interpretation.

## Install
`python scripts/fetch_model.py --tag model-bilstm_attn-20261110T162800Z-s7 --registry artifacts/models --promote` (default in the setup scripts).

---

## Previous model (v2): `lstm-20261110T111537Z-s7`

| Field | Value |
|---|---|
| Model | 1-layer LSTM (hidden 128), last + mean pooled state → softmax; same architecture as v1 (≈ 222k parameters) |
| What changed from v1 | training adds 4 raw-landmark variants per sequence simulating 8–30 fps, ≤ 15 % temporal crop and ≤ 15 % missed hand detections ([FPS_ROBUSTNESS.md](../research/FPS_ROBUSTNESS.md)) |
| Weights | [release `model-lstm-20261110T111537Z-s7`](https://github.com/nvaltryek-001/ISL-NOVA/releases/tag/model-lstm-20261110T111537Z-s7), tarball SHA-256 `55442ce395decd6210b8b92ba4680b81e2a2189c149437c3f188ed916418795c` |
| Trained by | GitHub Actions run [42804474143](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42804474143), config `ml/configs/lstm_fps_aug.json`, seed 7; 306 s of training on a 4-vCPU runner (NumPy, CPU) |
| Selection | best **validation** macro-F1 (95.8 %) among three seeds; the test split was not used for selection |
| Data | INCLUDE (Sridhar et al., ACM MM 2020, doi:10.1145/3394171.3413528), CC BY 4.0; dataset version `include-official-v1` |
| Split | INCLUDE official train / val / test lists: 2,448 / 272 / 635 (augmented variants come from train only) |
| Features | contract `isl-nova-fc-1.0.0` (32 × 204) |
| Calibration | temperature 0.975 (validation); rejection τ = 0.666 (keeps 95 % of correct validation predictions); margin 0.10 |

### Held-out test results (INCLUDE official test split, evaluated once)

| Metric | v2 (this model) | v1 |
|---|---:|---:|
| Top-1 accuracy | **92.0 %** | 91.7 % |
| Top-5 accuracy | **98.7 %** | 98.3 % |
| Macro precision / recall | 92.9 % / 92.6 % | 93.0 % / 92.4 % |
| Macro-F1 / weighted-F1 | 91.6 % / 91.6 % | 91.7 % / 91.5 % |
| Expected calibration error | **0.015** | 0.027 |
| `Predictor` end-to-end on all 635 | 91.97 % | 91.65 % |
| Decision states on the test split | 588 recognized · 32 uncertain · 15 unknown | 556 · 57 · 22 |
| Model latency (batched, per sample) | 0.23 ms | 0.73 ms (different runner) |
| Size | 1.78 MB | 1.78 MB |

Three-seed means (s7, s13, s21): fps-augmented LSTM **93.0 ± 0.7 %** top-1, baseline LSTM 90.6 ± 0.9 %.

Weakest classes on test (F1, support): Store or Shop 0.00 (3), Thursday 0.00 (1), Bad 0.40 (4), Slow 0.40 (4), Friend 0.50 (4), Computer 0.57 (3), Clothing 0.57 (4). With 1–4 test videos per class these figures are noisy.

### Browser pipeline (virtual camera, 73 held-out clips)

[Run 42807661120](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42807661120): **83.6 % top-1** (v1: 74.0 %), 97.3 % top-5; 54 recognized (49 correct), 14 uncertain, 5 unknown; median 9 fps on the CPU delegate; offline Python on the same clips 89.0 %. The v2 target of ≥ 85 % is **not met**. Not a live-person test.

### Unknown signs (open set)

[Run 42807661840](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42807661840), 887 sequences of 62 out-of-vocabulary INCLUDE glosses:

| Metric | v2 | v1 |
|---|---:|---:|
| AUROC (max calibrated probability) | **0.918** | 0.900 |
| Unknown signs wrongly *recognized* at the shipped τ | 34.0 % | **29.3 %** |
| Known test signs recognized **and** correct | **88.5 %** | 84.4 % |
| Best detector (combined, disjoint glosses), keep 90 %: FRR / FAR | **10.2 % / 13.7 %** | 13.2 % / 17.8 % |

v2 separates known from unknown better, but its validation-chosen τ is looser, so
**about 1 in 3 out-of-vocabulary signs is shown as a vocabulary sign**. The UI
always shows the decision state and top-5 alternatives; never act on a single
prediction. Details: [OPEN_SET_V2.md](../research/OPEN_SET_V2.md).

### Intended use
Isolated-sign recognition for practice, look-up and research in ISL NOVA. **Not** for interpretation in medical, legal, emergency or other high-stakes settings.

### Limitations
* **Not signer-independent** (INCLUDE has no signer IDs): no estimate for new people.
* **Narrow population**: one school in Chennai, studio conditions.
* **Weak unknown-sign rejection** (see above).
* **Vocabulary unverified**: labels are INCLUDE glosses; Hindi/Kannada meanings are machine drafts awaiting linguist review.
* **Isolated signs only**; no facial (non-manual) features.
* **No live-person or new-signer evaluation** has been run.

### Install
`python scripts/fetch_model.py --tag model-lstm-20261110T111537Z-s7 --registry artifacts/models --promote` (the setup scripts do this by default).

---

## Previous model (v1): `lstm-20261104T041414Z-s13`

Still served by the free Render demo (deployed from `feat/isl-nova-platform`).

| Field | Value |
|---|---|
| Model | 1-layer LSTM (hidden 128), last + mean pooled state → softmax; 221,896 parameters (≈ 222k) |
| Weights | [release `model-lstm-20261104T041414Z-s13`](https://github.com/nvaltryek-001/ISL-NOVA/releases/tag/model-lstm-20261104T041414Z-s13), tarball SHA-256 `e0979cd598c56bb839f3d689884e54bc7434e2cba47771c9ca3eaebdbfc543c0` |
| Trained by | GitHub Actions run [41771084083](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41771084083) (4-vCPU runner, NumPy, CPU), seed 13 |
| Training time | early stop at epoch 49 of max 60; job ≈ 8.5 min |
| Data | INCLUDE (Sridhar et al., ACM MM 2020, doi:10.1145/3394171.3413528), CC BY 4.0, downloaded from Zenodo 4010759 and processed in data run [41764539272](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41764539272) |
| Dataset version | `include-official-v1`: 3,370 landmark sequences for the 200 ISL NOVA classes |
| Split | INCLUDE official train / val / test lists: 2,448 / 272 / 635 used (15 insufficient-input sequences excluded) |
| Features | contract `isl-nova-fc-1.0.0` (32 × 204: hands, body-relative wrists and pose, two-hand distances, joint angles, presence, wrist velocity) from MediaPipe HandLandmarker + PoseLandmarker lite |
| Calibration | temperature 1.025, fitted on validation; rejection τ = 0.673 (keeps 95 % of correct validation predictions); margin 0.10 |

### Held-out test results (INCLUDE official test split, evaluated once)

| Metric | Value |
|---|---:|
| Top-1 accuracy | **91.7 %** |
| Top-5 accuracy | 98.3 % |
| Macro precision / recall | 93.0 % / 92.4 % |
| Macro-F1 / weighted-F1 | **91.7 %** / 91.5 % |
| Expected calibration error | 0.027 |
| Model latency (batched, per sample) | 0.73 ms |
| End-to-end latency through `Predictor` (features + model + decision) | 24 ms median, 36 ms p95 |
| Decision states on the test split | 556 recognized · 57 uncertain · 22 unknown |
| Size | 1.78 MB |

Weakest classes on test (F1, test support in brackets): Today 0.00 (1), Dress 0.29 (4), Bad 0.40 (4), Wife 0.40 (4), Friend 0.44 (4), Chair 0.50 (3), Clothing 0.50 (4). With 1–4 test videos per class, per-class figures carry wide uncertainty.

### Unknown-sign (open-set) evaluation

Scored on 635 known test sequences and 887 sequences of **62 INCLUDE glosses
outside the vocabulary**, never used in training or threshold selection
(run [41815223675](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41815223675)).

| Metric | Value |
|---|---:|
| AUROC (max calibrated probability) | **0.900** |
| Unknown signs wrongly *recognized* at τ = 0.673 | **29.3 %** |
| Unknown signs answered *uncertain* / *unknown* | 36.0 % / 34.3 % |
| Known signs recognized and correct at τ | 84.4 % |
| False acceptance / false rejection at τ | 29.3 % / 12.1 % |
| Unknown-detection precision / recall | 89.1 % / 70.7 % |

Full threshold sweep: [research/OPEN_SET_EVALUATION.md](../research/OPEN_SET_EVALUATION.md).

### Raw-video check (offline)

73 held-out INCLUDE test videos from Greetings, Seasons and Colours were run
from the raw video through the Python MediaPipe extractor, the feature contract
and this model (live-eval run [41774486592](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41774486592)):
**67 / 73 top-1 correct (91.8 %)**. Same signers as training.

### Browser pipeline check (virtual camera)

The same 73 clips played into headless Chromium as its webcam and recognised
through the Live Recognition page (in-browser MediaPipe on the CPU delegate,
~10 fps; [run 41860050670](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41860050670)): **74.0 % top-1**, 89.0 % top-5; 48 recognized (45 correct),
17 uncertain, 8 unknown. Lower than offline mainly because of the frame rate on
a 2-vCPU runner without a GPU. Not a live-person test.

### Comparison (same data, split, features and seed)

| Model | Val macro-F1 | Test top-1 | Test macro-F1 |
|---|---:|---:|---:|
| **LSTM** (selected by validation) | 91.1 % | 91.7 % | 91.7 % |
| Logistic regression on pooled statistics | 88.1 % | 89.1 % | 88.8 % |
| GRU | 86.7 % | 86.5 % | 86.1 % |
| DTW 1-NN | 80.7 % | 84.4 % | 83.5 % |

Single seed. Differences of a few points between models are within what seed variation could produce; repeat runs are on the roadmap.

### Intended use
Isolated-sign recognition for practice, look-up and research in ISL NOVA. **Not** for interpretation in medical, legal, emergency or other high-stakes settings.

### Limitations
* **Not signer-independent.** INCLUDE publishes no signer IDs, so test signers may appear in training. These numbers do **not** estimate accuracy on new people.
* **Narrow population.** INCLUDE was recorded with deaf students at one school in Chennai, under similar studio conditions. Accuracy on other signers, regions, lighting and webcams is unknown.
* **Weak unknown-sign rejection.** About 3 in 10 out-of-vocabulary signs are recognized as some vocabulary sign at the shipped threshold (see above). Always show alternatives; never act on a single prediction.
* **Vocabulary unverified.** Class labels are INCLUDE glosses, not reviewed ISL descriptions.
* **Isolated signs only**; no non-manual (facial) features.

### Reproduce
See README → *Train a model*. To install: `python scripts/fetch_model.py --tag model-lstm-20261104T041414Z-s13 --registry artifacts/models --promote`.
