# Research questions

| ID | Question | Primary metric | Data needed |
|---|---|---|---|
| RQ1 | How well do landmark-only temporal models recognise isolated ISL signs from signers **not seen in training**? | macro-F1 and top-1 on a signer-independent test set | ≥ 10 consented signers with signer IDs |
| RQ2 | Which feature blocks contribute most (hand-local shape, two-hand relations, body-relative trajectory, velocity, joint angles)? | Δ macro-F1 under block ablation | as RQ1 |
| RQ3 | How reliably can a calibrated classifier reject signs outside its vocabulary? | AUROC (max-prob), known-accept and unknown-reject rates at τ; ECE | held-out "unknown" classes (e.g. INCLUDE reserve glosses) |
| RQ4 | How does performance vary with lighting, camera distance and signing speed? | per-condition macro-F1 | session environment metadata |
| RQ5 | How large is the gap between the INCLUDE official split and a signer-independent split? | Δ macro-F1 | INCLUDE + new signer-labelled data |

## Hypotheses (to be tested, not assumed)
* H1: body-relative wrist trajectories and two-hand relations matter more for two-handed signs than hand shape alone.
* H2: temperature scaling reduces ECE without changing top-1.
* H3: the official INCLUDE split overestimates signer-independent performance.

The systematic literature review protocol is _TBD_.
