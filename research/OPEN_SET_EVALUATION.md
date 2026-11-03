# Open-set evaluation

**Goal:** a sign outside the vocabulary should be answered *unknown*, not mapped to the nearest known class.

* **Scores:** calibrated max-softmax probability (Hendrycks & Gimpel 2017) after temperature scaling (Guo et al. 2017), plus a top-1/top-2 margin.
* **Threshold:** τ keeps 95 % of *correct validation* predictions (`choose_threshold`). The decision rule is recognized if p ≥ τ and margin ≥ m; uncertain if p ≥ 0.6 τ; else unknown.
* **Unknown set:** manifest `open_set_entries`, made of classes never used in training. The 63 INCLUDE reserve glosses are a natural candidate.
* **Metrics:** AUROC (known vs unknown max-prob), known-accept rate and unknown-reject rate at τ (`open_set_report`).
* **Caveat:** max-softmax is a baseline. Stronger detectors are future work.
