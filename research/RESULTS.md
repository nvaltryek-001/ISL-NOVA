# Results: INCLUDE official split, 200 classes

All values come from `metrics.json` files written by training run [41771084083](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41771084083) and are reproduced in that run's step summary and in the [model release](https://github.com/nvaltryek-001/ISL-NOVA/releases/tag/model-lstm-20261104T041414Z-s13) (`comparison.json`, `verify.json`).

| Field | Value |
|---|---|
| Commit | `50bc027` (training run settings), pipeline code from `9b4de21` |
| Dataset version | `include-official-v1` (data run 41764539272: 44/44 Zenodo parts, 56.75 GB, MD5-verified) |
| Split policy | INCLUDE official train/val/test lists. **Not signer-independent** (INCLUDE has no signer IDs) |
| Classes / samples | 200 classes · train 2,448 · val 272 · test 635 |
| Seeds | 1 (seed 13) |

| Model | Top-1 | Top-5 | Macro-P | Macro-R | Macro-F1 | Weighted-F1 | ECE | Latency (ms) | Size |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LSTM | 91.7 % | 98.3 % | 93.0 % | 92.4 % | 91.7 % | 91.5 % | 0.027 | 0.73 | 1.78 MB |
| Pooled LogReg | 89.1 % | 98.3 % | 90.4 % | 89.9 % | 88.8 % | 88.9 % | 0.024 | 0.02 | 0.99 MB |
| GRU | 86.5 % | 97.6 % | 88.0 % | 87.4 % | 86.1 % | 85.8 % | 0.017 | 0.17 | 1.44 MB |
| DTW 1-NN | 84.4 % | 94.6 % | 85.7 % | 84.8 % | 83.5 % | 83.8 % | 0.040 | 130.4 | 63.95 MB |

**Research questions status.** RQ5 (official vs signer-independent gap) and RQ1 still need signer-labelled data; RQ3 (open set) is now measured on 62 INCLUDE reserve glosses: AUROC 0.900, 29.3 % of unknown sequences wrongly recognized at τ (see [OPEN_SET_EVALUATION.md](OPEN_SET_EVALUATION.md)); RQ2 ablations and multi-seed repeats are not yet run.

## Additional genuine evaluations (2026-11-04)

| Evaluation | Run | Result |
|---|---|---|
| Unknown-sign detection, 635 known vs 887 unknown (62 glosses) | [41815223675](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41815223675) | AUROC 0.900; unknown false-recognition 29.3 %; known recognized-and-correct 84.4 % |
| Raw held-out video → Python MediaPipe → model (offline) | [41774486592](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41774486592) | 67 / 73 top-1 correct (91.8 %) |
| Same 73 clips as a virtual webcam through the Live page (browser MediaPipe, CPU delegate ~10 fps) | [41860050670](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41860050670) | 74.0 % top-1, 89.0 % top-5; 45/48 *recognized* correct; 17 uncertain, 8 unknown |
| Unknown-sign false acceptance / false rejection at τ | 41815223675 | 29.3 % / 12.1 %; unknown-detection precision 89.1 %, recall 70.7 % |
| New-signer evaluation | — | workflow implemented; **no new-signer data exists, no result** |

## v2 results (2026-11-10)

Same dataset version, split, feature contract and evaluation rules. Released v2
model: [`model-lstm-20261110T111537Z-s7`](https://github.com/nvaltryek-001/ISL-NOVA/releases/tag/model-lstm-20261110T111537Z-s7)
(LSTM + frame-rate augmentation, seed 7, chosen by validation macro-F1). Details:
[FPS_ROBUSTNESS.md](FPS_ROBUSTNESS.md), [OPEN_SET_V2.md](OPEN_SET_V2.md).

| Model (test split, 635) | Seeds | Top-1 | Top-5 | Macro-F1 | ECE |
|---|---:|---:|---:|---:|---:|
| **LSTM + fps aug (released, s7)** | 1 | **92.0 %** | **98.7 %** | 91.6 % | 0.015 |
| LSTM + fps aug, mean ± std | 3 | 93.0 ± 0.7 % | — | 92.7 ± 0.8 % | — |
| LSTM baseline, mean ± std | 3 | 90.6 ± 0.9 % | — | 90.3 ± 1.2 % | — |
| GRU + fps aug (s13) | 1 | 93.2 % | — | 93.3 % | — |

| Evaluation (v2 model) | Run | Result |
|---|---|---|
| Training matrix (6 models) | [42804474143](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42804474143) | table above |
| Virtual camera, 73 held-out clips through the Live page | [42807661120](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42807661120) | **83.6 % top-1** (v1: 74.0 %), 97.3 % top-5; 49/54 *recognized* correct; offline on the same clips 89.0 % |
| Unknown signs, all 62 reserve glosses, shipped τ = 0.666 | [42807661840](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42807661840) | AUROC 0.918; **34.0 %** of unknown sequences *recognized* (v1: 29.3 %); known recognized-and-correct 88.5 % |
| Detector comparison, disjoint unknown glosses | 42807661840 | best: combined, AUROC 0.932; keep-90 %: FRR 10.2 % / FAR 13.7 % |
| Practice Coach similarity, 120 test recordings vs train references (local) | — | own-sign median 93 vs other-sign median 13; own > other in 88 % of pairs |

**Targets not met:** browser top-1 ≥ 85 % (83.6 %); unknown-sign FAR < 10 % with FRR ≤ 15 % (best 11.5 % / 12.9 %). Still **not signer-independent**; still **no live-person or new-signer result**.

## v3 results (2026-11-10)

Run [42851786127](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42851786127); details in [V3_MODELS.md](V3_MODELS.md).

| Measured | v3 BiLSTM-attention (selected) | Target |
|---|---:|---|
| Test top-1 / top-5 (635) | **95.1 % / 99.4 %** | — |
| Test macro-F1 / ECE | 94.1 % / 0.013 | — |
| Unknown signs accepted, part B (shipped detector) | **8.8 %** | < 10 % — met |
| Known signs not recognized, part B | **13.2 %** | ≤ 15 % — met |
| Browser pipeline, 73 held-out clips | **84.9 %** ([run 42859291767](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42859291767)) | ≥ 85 % — not met |
| Best ensemble (not selected) | 97.2 % test top-1 | — |

Still **not signer-independent**; still **no live-person, new-signer or user-study result**.

## v4: face features (2026-11-11)

Contract 2.0.0 (hands + pose + 51 face values), runs [42957883286](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42957883286) (data) and [42964878980](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42964878980) (training). Three-seed test top-1: BiLSTM-attention 95.8 % (v3 94.5 %), Transformer 96.4 % (95.7 %), TCN 95.0 % (95.9 %); best single 97.3 %. Selected face model: 95.1 % top-1, unknown signs accepted 14.2 % (target < 10 % missed). The default stays v3 ([V4_FACE_FEATURES.md](V4_FACE_FEATURES.md)).
