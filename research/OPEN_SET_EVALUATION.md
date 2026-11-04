# Open-set evaluation

**Goal:** a sign outside the vocabulary should be answered *unknown*, not mapped to the nearest known class.

* **Scores:** calibrated max-softmax probability (Hendrycks & Gimpel 2017) after temperature scaling (Guo et al. 2017), plus a top-1/top-2 margin.
* **Threshold:** τ keeps 95 % of *correct validation* predictions (`choose_threshold`). The decision rule is recognized if p ≥ τ and margin ≥ m; uncertain if p ≥ 0.6 τ; else unknown.
* **Unknown set:** manifest `open_set_entries`, made of classes never used in training. The 63 INCLUDE reserve glosses are a natural candidate.
* **Metrics:** AUROC (known vs unknown max-prob), known-accept rate and unknown-reject rate at τ (`open_set_report`).
* **Caveat:** max-softmax is a baseline. Stronger detectors are future work.

## Results: INCLUDE reserve glosses (genuine, run 41815223675)

Model `lstm-20261104T041414Z-s13` (the released 200-class LSTM), unchanged; the
unknown classes were never used for training, calibration or choosing τ.

* **Known:** 635 sequences, INCLUDE official test split of the 200 classes.
* **Unknown:** 887 sequences of **62 INCLUDE glosses outside the vocabulary**
  (data run [41773683352](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41773683352),
  dataset `include-official-v2`); 883 had enough landmarks to score.

| Metric | Value |
|---|---:|
| AUROC, max calibrated probability (known vs unknown) | **0.900** |
| Unknown signs **wrongly recognized** as a vocabulary sign (production τ = 0.673, margin 0.10) | **29.3 %** (260 / 887) |
| Unknown signs answered *uncertain* or *unknown* | 70.2 % (319 uncertain + 304 unknown) |
| Known test signs recognized **and correct** | 84.4 % (536 / 635) |
| Known test signs recognized but wrong | 3.5 % |
| Known test states | 558 recognized · 54 uncertain · 23 unknown |
| Unknown accepted at the threshold keeping 95 % of known (p ≥ 0.464) | 55.3 % |

Threshold sweep (fraction of known test sequences whose top probability passes
the threshold vs fraction of unknown sequences rejected):

| Threshold | 0.40 | 0.50 | 0.60 | 0.70 | 0.80 | 0.90 |
|---|---:|---:|---:|---:|---:|---:|
| Known accepted | 96.7 % | 93.7 % | 89.9 % | 86.8 % | 82.4 % | 75.3 % |
| Unknown rejected | 33.5 % | 49.9 % | 63.2 % | 73.6 % | 82.7 % | 91.8 % |

**Reading.** Max-softmax separates in-vocabulary from out-of-vocabulary signs
reasonably (AUROC 0.90) but not well enough to stop false recognitions: almost
**three in ten unseen signs are confidently mapped to a known sign** at the
shipped threshold. The UI therefore always shows the top-5 alternatives and the
state, and never speaks a result automatically. Raising τ to ≈0.80 halves false
recognitions but rejects ~18 % of correct known signs. Better detectors
(energy scores, an explicit background class, embedding distance) are open work.

**Scope.** Same signers and studio conditions as training; not an unseen-signer
evaluation. Report and per-sequence rows: `open_set.json`, `open_set_rows.csv`
on the [model release](https://github.com/nvaltryek-001/ISL-NOVA/releases/tag/model-lstm-20261104T041414Z-s13).
