# Experiment protocol

1. **Fix the dataset version** (manifest SHA-256) and the feature contract (`isl-nova-fc-1.0.0`).
2. **Splits:** the source's official split if it has one (INCLUDE); otherwise signer-independent (seeded). Training aborts on signer, session or hash leakage.
3. **Candidates:** `lstm` (baseline), `gru`, `pooled_logreg`, `dtw_1nn`; later TCN and Temporal Transformer in PyTorch, all with identical splits and preprocessing.
4. **Training:** Adam, inverse-sqrt class weighting, augmentation (scale ±8 %, rotation ±8°, temporal shift ±2 frames, Gaussian noise; **no mirroring**, because hand roles can be lexical), early stopping on **validation** macro-F1, LR halving on plateau, fixed seeds.
5. **Selection:** by validation macro-F1 only. Temperature and τ are fitted on validation.
6. **Test:** evaluated **once** per selected model. Report top-1, top-5, macro- and weighted-F1, per-class precision/recall/F1, confusion matrix, ECE, open-set metrics, per-signer accuracy, latency and model size (all written to `metrics.json` automatically).
7. **Repeats:** ≥ 3 seeds; report mean ± std.
8. **Provenance:** keep `model.json`, `metrics.json` and `training_log.jsonl`; record the commit hash.

Configs: `ml/configs/*.json`. Runner: `python -m isl_nova_ml.train`, or *AI Laboratory → Experiments*.
