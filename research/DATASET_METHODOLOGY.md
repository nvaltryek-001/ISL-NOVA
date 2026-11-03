# Dataset methodology

1. **Vocabulary:** 200 slots chosen from INCLUDE's 263 classes (selection rules in `dataset/README.md`; the 63 reserve glosses and their reasons are in `reserve_candidates.csv`). Slots are stable and never reused.
2. **Linguistic verification:** each slot moves `reference_found → review_pending → verified|rejected`, decided by a reviewer with the `linguist` role. Every transition has a mandatory note in `verification_events`. Hindi and Kannada meanings are entered and verified separately.
3. **Recording:** see `docs/DATASET_PROTOCOL.md §3`. Target per class: ≥ 10 approved clips from ≥ 3 signers (the training-readiness threshold), and ≥ 20 from ≥ 5 signers for robust evaluation.
4. **Variation:** sessions vary lighting (indoor-even / window / dim), background (plain / cluttered), distance (near / medium / far) and speed. Signer hand dominance is recorded.
5. **Quality control:** automatic checks at upload, four-eyes annotation review, and dataset validation before every version.
6. **Versioning:** immutable versions with a seeded signer-independent split and a leakage report; the manifest SHA-256 is stored in each model's lineage.
7. **Reporting:** every dataset version reports counts by class, signer and session, imbalance, and how many recordings were excluded for missing training consent.
