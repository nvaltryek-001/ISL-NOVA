# Model card: `lstm-20261104T041414Z-s13`

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

## Held-out test results (INCLUDE official test split, evaluated once)

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

## Unknown-sign (open-set) evaluation

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

## Raw-video check (offline)

73 held-out INCLUDE test videos from Greetings, Seasons and Colours were run
from the raw video through the Python MediaPipe extractor, the feature contract
and this model (live-eval run [41774486592](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41774486592)):
**67 / 73 top-1 correct (91.8 %)**. Same signers as training.

## Browser pipeline check (virtual camera)

The same 73 clips played into headless Chromium as its webcam and recognised
through the Live Recognition page (in-browser MediaPipe on the CPU delegate,
~10 fps; [run 41860050670](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41860050670)): **74.0 % top-1**, 89.0 % top-5; 48 recognized (45 correct),
17 uncertain, 8 unknown. Lower than offline mainly because of the frame rate on
a 2-vCPU runner without a GPU. Not a live-person test.

## Comparison (same data, split, features and seed)

| Model | Val macro-F1 | Test top-1 | Test macro-F1 |
|---|---:|---:|---:|
| **LSTM** (selected by validation) | 91.1 % | 91.7 % | 91.7 % |
| Logistic regression on pooled statistics | 88.1 % | 89.1 % | 88.8 % |
| GRU | 86.7 % | 86.5 % | 86.1 % |
| DTW 1-NN | 80.7 % | 84.4 % | 83.5 % |

Single seed. Differences of a few points between models are within what seed variation could produce; repeat runs are on the roadmap.

## Intended use
Isolated-sign recognition for practice, look-up and research in ISL NOVA. **Not** for interpretation in medical, legal, emergency or other high-stakes settings.

## Limitations
* **Not signer-independent.** INCLUDE publishes no signer IDs, so test signers may appear in training. These numbers do **not** estimate accuracy on new people.
* **Narrow population.** INCLUDE was recorded with deaf students at one school in Chennai, under similar studio conditions. Accuracy on other signers, regions, lighting and webcams is unknown.
* **Weak unknown-sign rejection.** About 3 in 10 out-of-vocabulary signs are recognized as some vocabulary sign at the shipped threshold (see above). Always show alternatives; never act on a single prediction.
* **Vocabulary unverified.** Class labels are INCLUDE glosses, not reviewed ISL descriptions.
* **Isolated signs only**; no non-manual (facial) features.

## Reproduce
See README → *Train a model*. To install: `python scripts/fetch_model.py --tag model-lstm-20261104T041414Z-s13 --registry artifacts/models --promote`.
