# Performance benchmark

**These are engineering latency measurements, not recognition results.** They use synthetic landmark sequences and untrained (randomly initialised) models of realistic size.

Command: `PYTHONPATH=backend:ml python scripts/benchmark.py`
Machine: build sandbox, 2 vCPU, Linux x86-64, Python 3.13.18. Measured 2026-11-03.

| Operation | Median (ms) | p95 (ms) | n |
|---|---:|---:|---:|
| Feature extraction (45 frames → 32×204) | 18.78 | 34.22 | 200 |
| LSTM inference, h = 128, 200 classes (221,896 params) | 2.67 | 3.25 | 100 |
| GRU inference, h = 128, 200 classes (179,400 params) | 1.76 | 2.51 | 100 |
| Pooled logistic regression, 200 classes | 0.13 | 0.21 | 200 |
| `GET /api/v1/signs?q=good` (in-process, SQLite) | 3.51 | 5.80 | 100 |
| `GET /api/v1/dataset/stats` | 2.58 | 3.33 | 100 |
| `POST /api/v1/predict/sequence` (no model loaded) | 10.58 | 13.60 | 100 |

Interpretation: server-side inference per window fits comfortably inside the 750 ms continuous-recognition interval; feature extraction dominates. In-browser MediaPipe throughput could not be measured (CDN unavailable in the sandbox).

Recognition metrics (top-1, macro-F1, ECE, open-set AUROC, per-signer) will be reported here and in [MODEL_CARD.md](MODEL_CARD.md) only after training on authentic data.
