# Unknown-sign detection v2: detector comparison

**Run:** GitHub Actions [42804676703](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42804676703), model `lstm-20261104T041414Z-s13` (unchanged). Report: `open_set_v2.json` on the [model release](https://github.com/nvaltryek-001/ISL-NOVA/releases/tag/model-lstm-20261104T041414Z-s13). Code: `ml/isl_nova_ml/openset.py`, `include_pipeline open-set-v2`.

## Protocol (no leakage)

The 62 out-of-vocabulary INCLUDE glosses are split **by gloss** into two disjoint halves (hash of the gloss name): 31 glosses / 439 sequences in A, 31 glosses / 444 sequences in B.

| Set | Known signs | Unknown signs | Used for |
|---|---|---|---|
| Fit | validation split (271) | half A | fitting the combined detector and choosing every threshold |
| Eval | test split (635) | half B (never seen) | all numbers below |

Class centroids are fitted on the training split only.

## Detectors

| Detector | Score |
|---|---|
| maxprob (current production) | calibrated top-1 probability |
| margin | top-1 minus top-2 probability |
| entropy | negative entropy of the calibrated distribution |
| centroid | negative Mahalanobis distance of time-pooled features to the nearest class mean (Ledoit-Wolf) |
| combined | logistic regression on the four scores, fitted on the fit set |

## Results on the eval set

FRR = known test signs rejected · FAR = unknown signs accepted as a known sign. The threshold keeps 95 / 90 / 85 % of known **validation** signs.

| Detector | AUROC | keep 95 %: FRR / FAR | keep 90 %: FRR / FAR | keep 85 %: FRR / FAR |
|---|---:|---:|---:|---:|
| maxprob | 0.901 | 7.6 / 42.3 % | 15.9 / 22.3 % | 19.5 / 14.0 % |
| margin | 0.887 | 9.1 / 42.6 % | 14.8 / 26.1 % | 20.6 / 14.2 % |
| entropy | 0.913 | 7.9 / 37.2 % | **12.8 / 21.6 %** | 18.3 / 12.2 % |
| centroid | 0.803 | 6.6 / 74.5 % | 11.5 / 54.1 % | 16.7 / 44.4 % |
| **combined** | **0.921** | **6.9 / 34.5 %** | **13.2 / 17.8 %** | 17.0 / 14.9 % |

## Reading

- The combined detector is the best at every operating point. At ~13 % false rejection it accepts **17.8 %** of unknown signs, against 22.3 % for the max-probability baseline at a similar rejection rate.
- Entropy alone is a simple, strong improvement with no extra fitting.
- Class-centroid distance on pooled features is weak on its own.
- **The specification target (FAR < 10 % with FRR ≤ 15 %) is not met by any detector.** The closest is combined/entropy at 85 % keep (FAR 12–15 %, FRR 17–18 %).

## Repeat with the v2 model (frame-rate augmentation)

**Run:** [42807661840](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42807661840), model `lstm-20261110T111537Z-s7`, identical protocol and halves (fit: 271 val + 439 unknown A; eval: 635 test + 444 unknown B).

| Detector | AUROC | keep 95 %: FRR / FAR | keep 90 %: FRR / FAR | keep 85 %: FRR / FAR |
|---|---:|---:|---:|---:|
| maxprob | 0.915 | 6.8 / 37.6 % | 12.9 / 17.1 % | 16.5 / 11.3 % |
| margin | 0.904 | 7.9 / 38.3 % | 13.4 / 20.3 % | 18.0 / 10.4 % |
| entropy | 0.925 | 6.5 / 29.3 % | 11.2 / 16.7 % | 16.4 / 9.9 % |
| centroid | 0.803 | 6.6 / 74.5 % | 11.5 / 54.1 % | 16.7 / 44.4 % |
| **combined** | **0.932** | **5.5 / 30.4 %** | **10.2 / 13.7 %** | 12.9 / 11.5 % |

The v1-style evaluation of the same run (all 62 unknown glosses, shipped τ = 0.666 chosen on validation only):

| | v1 model `…041414Z-s13` | v2 model `…111537Z-s7` |
|---|---:|---:|
| AUROC (max probability) | 0.900 | **0.918** |
| Unknown signs *recognized* at the shipped τ | **29.3 %** | 34.0 % |
| Known test signs recognized **and** correct | 84.4 % | **88.5 %** |
| Known recognized but wrong | — | 4.1 % |

Reading: the v2 model separates known from unknown signs better at every
matched operating point (combined detector at ~10 % FRR: FAR 13.7 % vs 17.8 %),
but its validation-chosen τ lands at a looser point, so **more unknown signs are
recognized at the shipped threshold (34.0 % vs 29.3 %)** while more known signs
are accepted correctly. The target (FAR < 10 %, FRR ≤ 15 %) is **still not met**;
closest is combined at keep 85 % (FRR 12.9 %, FAR 11.5 %).

## Next steps

1. Train with an explicit `__other__` class from half-A glosses plus idle and fidget movement; evaluate on half B.
2. Ship the combined detector in the `Predictor` (store its weights with the model, report it in the model card).
3. Re-check on new signers once real recordings exist.
4. ~~Repeat with the frame-rate-augmented models~~ done above (see also `FPS_ROBUSTNESS.md`).
5. Choose τ on a detector operating point (e.g. combined keep 90 %) rather than on known-validation coverage alone.
