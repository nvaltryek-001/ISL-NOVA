# Practice Coach, Text to Sign and Conversation

## Reference data

`dataset/scripts/build_references.py` builds `references_v1.npz` from the **INCLUDE training split only** (CC BY 4.0, landmarks, no video). For each of the 200 signs it stores:

- `templates`: the mean 32 × 204 feature-contract sequence;
- one **medoid** training recording (the one closest to the template), at 12.5 fps, for skeleton animation;
- distance calibration: the median distance of training recordings to their own template (`same`) and to other signs' templates (`other`), plus the same-sign median per feature block.

It is published as release [`references-v1`](https://github.com/nvaltryek-001/ISL-NOVA/releases/tag/references-v1) by `publish-references.yml` (4.8 MB, SHA-256 checked). It is installed by `scripts/fetch_references.py`, which the Windows/Linux/macOS setup scripts and the Docker entrypoint call. The server reads it from `REFERENCES_DIR` (default `dataset/references`). Without it, the practice endpoints answer `503 references_unavailable` and the UI says so.

## Scoring (`POST /api/v1/practice/score`)

1. The attempt's landmarks go through the same feature contract as recognition.
2. Distance `d` = RMS difference to the target sign's template.
3. Similarity = `100 × clip((other − d) / (other − same), 0, 1)`.
4. Each feature block (left/right hand shape, finger bends, hand position, arm posture, two-hand distance, hands used, movement) is compared with its own same-sign median: `good` ≤ 1.2×, `check` ≤ 1.8×, else `different`. Up to three tips are given for the worst parts.
5. If a model is active, its top-3 reading of the attempt is returned, with whether it matches the target.

**Validation on held-out data (local run, 2026-11-10):** 120 random INCLUDE **test** recordings were scored against their own sign and against a random other sign. Median similarity was 93 (own) vs 13 (other), and the own sign scored higher in 88 % of pairs. This shows the score separates signs on INCLUDE signers. It has not been validated with learners or ISL teachers.

**Limits:** references come from INCLUDE signers and the signs are not linguistically verified. The score measures similarity to those recordings, not correctness of ISL. Regional variants will score lower.

## Text to Sign (`/text-to-sign`)

Text in English, Hindi or Kannada is split into words. The longest phrase (up to 3 words) that exactly matches a sign's English gloss or a Hindi or Kannada meaning is shown as that sign's reference animation. Words without a sign are listed as "no sign in vocabulary".

The page states that the result is **a sequence of individual signs, not an ISL translation** (ISL has its own grammar and word order).

## Conversation (`/conversation`)

- **Signer side:** camera + in-browser MediaPipe. Every 0.9 s the last 2 s window is classified. Only `recognized` answers are accepted, and a repeat of the same sign within 4 s is ignored. The meaning appears in the chosen language and is spoken (`en-IN`, `hi-IN`, `kn-IN`); draft meanings carry a Draft badge.
- **Speaker side:** browser speech recognition (Chrome/Edge; other browsers show "not supported"). Final phrases appear in the transcript, and matching vocabulary signs are animated.
- Large-text transcript with `aria-live`. The page states that this is word-by-word assistance, not interpretation.

## Tests

- `backend/tests/test_practice.py`: unavailable state, reference endpoint, own-sign attempt scoring higher than another sign's, insufficient input.
- E2E: Text to Sign matches English (`good morning` as a two-word phrase, `teacher`) and Hindi (`नमस्ते`, `दोस्त`) and flags unknown words. The Practice Coach shows the reference and keeps the attempt button disabled until the camera runs. All 3 new routes are included in the heading, accessibility and responsive checks.
