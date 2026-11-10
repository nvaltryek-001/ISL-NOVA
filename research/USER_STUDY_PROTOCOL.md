# User study protocol: real people and new signers

**Status: protocol and tooling ready; no study has been run and no results exist.** Nothing in this repository reports real-person or new-signer accuracy.

## Questions

1. How accurate is live webcam recognition for people who are **not** in INCLUDE (new signers)?
2. How often does the system say *uncertain* or *unknown*, and how often is a *recognized* answer wrong?
3. Do learners find the Practice Coach feedback useful?

## Participants

- **Signers:** 5–10 adult signers not in INCLUDE, ideally Deaf ISL users or fluent interpreters, with a mix of hand dominance, age and region. Pseudonymous IDs only.
- **Reviewer:** one qualified ISL reviewer (Deaf signer or accredited interpreter) confirms that each recorded sign is the intended sign.

## Consent and data

- Written, informed consent before any recording, using the app's consent form (`isl-nova-consent-v1`). Scopes: `research_evaluation` (required) and `model_training` (optional, separate).
- Participants can withdraw at any time. Withdrawal erases their recordings (built into the app).
- Retention: a set end date (e.g. 12 months) entered on the consent record.
- Raw video stays on the project server. Reports contain only aggregate figures and pseudonymous IDs. No faces appear in any publication.

## Procedure (per signer, about 45 minutes)

1. Register a pseudonymous signer, record consent, and open a session noting lighting, background, camera and distance.
2. Signs: 30 from the 200-sign vocabulary (stratified by category), 3 repetitions each, in random order shown by the Recording Studio.
3. Conditions: normal indoor light; a second session in dim light or a busy background for robustness (optional).
4. Each recording gets an annotation, and a second person approves it (four-eyes rule built into the app).
5. Freeze a dataset version containing only this study's approved recordings.

## Analysis

- Run **AI Laboratory → New signers → Evaluate** on the frozen version (`POST /api/v1/evaluation/runs`). The production model is applied exactly as in live use.
- Report:
  - top-1 and top-5 per signer and overall;
  - state counts, and precision of *recognized* answers;
  - confusion between signs;
  - the number of signers and recordings.
- Report these numbers **separately** from the INCLUDE test results. Do not average them together.
- With fewer than about 10 signers, describe results as indicative, not as a measure of generalisation.

## Live webcam session (optional)

Signers use **Live Recognition** in capture mode. The facilitator records the intended sign and the app's answer and state for 20 signs (the app's history export can help). Report these separately as "live, real person".

## Ethics

Obtain institutional ethics approval where required before recruiting. Pay participants fairly. Provide information in ISL (interpreter present) and in writing.
