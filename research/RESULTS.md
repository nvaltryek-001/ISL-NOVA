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

**Research questions status.** RQ5 (official vs signer-independent gap) and RQ1 still need signer-labelled data; RQ3 (open set) needs held-out unknown classes, such as the 63 INCLUDE reserve glosses, which this run did not extract; RQ2 ablations and multi-seed repeats are not yet run.
