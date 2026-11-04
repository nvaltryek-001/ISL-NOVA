# Signer-independent protocol

* Every recording carries a pseudonymous `signer_id` and a `session_id`.
* `assign_splits` (ml/isl_nova_ml/data.py) shuffles signers with a fixed seed and assigns ≈15 % of signers to test, ≈15 % to validation and the rest to train. No signer appears in two partitions.
* `leakage_report` fails the run if any signer, session or file hash spans partitions, or if any recording ID is duplicated.
* With fewer than 3 signers no valid signer-independent split exists, and dataset validation warns.
* Sources without signer IDs (INCLUDE) use `unknown:<source>`. They are excluded from the leakage comparison and counted in `signer_ids_unknown`. Results on such data **must not** be described as signer-independent.
* Report per-signer test accuracy (written to `metrics.json` as `per_signer_test`).

## New-signer evaluation workflow (implemented; no results yet)

The released model was trained and tested on INCLUDE, which publishes no signer
IDs, so **no unseen-signer accuracy has been measured** and none is claimed.
The platform provides the workflow to measure it once consented recordings from
people who are not in INCLUDE exist:

1. Record signers with consent (Dataset → Recordings / personal capture); each
   recording gets a pseudonymous `signer_id`. Do not use INCLUDE videos.
2. A data curator builds and freezes a dataset version from those recordings
   (Dataset → Versions). Only approved, consented recordings are included.
3. A researcher opens **AI Lab → New signers**, selects the version and clicks
   **Evaluate** (`POST /api/v1/evaluation/runs`). The production model runs on
   every entry through the same `Predictor` as live recognition; the job
   stores overall top-1/top-5, state counts and **per-signer** accuracy
   (`evaluation_results`, split `new_signer`).
4. Results are listed in the tab and at `GET /api/v1/evaluation/runs/{id}`.
   Report the number of signers and recordings with any figure; a handful of
   signers does not establish generalisation.

Tested: `test_new_signer_evaluation_run` (backend, synthetic recordings only —
it checks the plumbing and per-signer aggregation, not model quality).
