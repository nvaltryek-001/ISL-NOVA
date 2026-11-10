# Vocabulary expansion plan: 200 → 500 signs

**Current size: 200 signs (ISL001–ISL200).** No sign beyond ISL200 exists until it is accepted through the proposal workflow. Nothing here claims 500 signs are available.

## Why expand, and where

INCLUDE-derived categories leave gaps that matter for daily communication:

| Gap | Today | Target additions |
|---|---:|---:|
| Everyday actions / verbs (eat, drink, go, come, want, help, sleep, work…) | 2 | +60 |
| Food and daily needs (water, rice, tea, milk, roti, toilet…) | 16 | +40 |
| Question words (what, where, when, who, why, how, how much) | 0 | +10 |
| Emergencies and health (help, pain, ambulance, fire, danger, fever…) | few | +30 |
| Numbers 0–20, tens, money amounts | partial | +30 |
| Places and transport in Indian contexts (temple, auto-rickshaw, bus stop…) | partial | +40 |
| Feelings, family, school and work extensions | partial | +90 |
| **Total** | **200** | **+300 → 500** |

## Workflow (implemented)

1. **Propose:** any signed-in user submits a gloss, category, meanings (en/hi/kn) and an optional licensed reference URL (`POST /api/v1/vocabulary/proposals`). Duplicates are refused: the normalised gloss must not match an existing sign or a pending proposal. Direct sign creation applies the same check.
2. **Review:** a linguist accepts or rejects (`POST /api/v1/vocabulary/proposals/{id}/decide`). A rejection needs a note, and the proposer is notified.
3. **Accept:** creates the next stable ID (ISL201, ISL202, …) with status `proposed`, data readiness `no_data`, and hi/kn meanings as drafts. IDs are never reused.
4. **Collect:** consented recordings through the Recording Studio, with the four-eyes review. A class is training-ready with a verified sign, ≥ 10 approved recordings and ≥ 3 signers.
5. **Version:** freeze a dataset version; train; evaluate signer-independently (now possible because recordings carry signer IDs).

## Sources

Only sources whose licence permits it, documented in `dataset/sources/`:

- new consented recordings (preferred);
- other ISL datasets after a licence review. iSign is CC BY-NC-SA and gated, so it is not used for a commercial-compatible release without review. ISLRTC has no established reuse licence, so it is reference only.

## Milestones

| Milestone | Signs | Needs |
|---|---:|---|
| M1 | 260 | 60 verbs + question words proposed, accepted and recorded by ≥ 3 signers |
| M2 | 350 | food, emergency, numbers |
| M3 | 500 | remaining categories; ≥ 10 signers per class |
