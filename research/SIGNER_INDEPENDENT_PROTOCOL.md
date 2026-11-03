# Signer-independent protocol

* Every recording carries a pseudonymous `signer_id` and a `session_id`.
* `assign_splits` (ml/isl_nova_ml/data.py) shuffles signers with a fixed seed and assigns ≈15 % of signers to test, ≈15 % to validation and the rest to train. No signer appears in two partitions.
* `leakage_report` fails the run if any signer, session or file hash spans partitions, or if any recording ID is duplicated.
* With fewer than 3 signers no valid signer-independent split exists, and dataset validation warns.
* Sources without signer IDs (INCLUDE) use `unknown:<source>`. They are excluded from the leakage comparison and counted in `signer_ids_unknown`. Results on such data **must not** be described as signer-independent.
* Report per-signer test accuracy (written to `metrics.json` as `per_signer_test`).
