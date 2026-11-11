# v4: non-manual (face) features — feature contract 2.0.0

**Question.** ISL grammar uses the face (eyebrows, mouth, eyes). Do face landmarks improve
recognition of the 200 isolated signs?

## Data

All 4,257 INCLUDE videos (3,370 vocabulary + 887 out-of-vocabulary) were extracted again with
MediaPipe FaceLandmarker in addition to hands and pose: data run
[42957883286](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42957883286), artifact
`landmarks-include-face-v1`. The face is too small for the face detector in full-body frames, so the
head is cropped around the pose nose and upscaled first. **Face found in 99.94 % of 273,515 frames.**
Feature contract `isl-nova-fc-2.0.0` = the 204 features of 1.0.0 + a 51-value face block
([FEATURE_CONTRACT.md](../docs/FEATURE_CONTRACT.md)).

## Training

Round [42964878980](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42964878980): the same
architectures, augmentation and seeds as v3, trained on contract 2.0.0; the v3 default competed on
validation. Official split; **not signer-independent**.

### Test top-1, three seeds (7, 13, 21)

| Architecture | Hands + pose (v3) | + face (v4) | Change |
|---|---:|---:|---:|
| BiLSTM-attention | 94.5 ± 0.5 % | **95.8 ± 0.8 %** | +1.3 |
| Transformer | 95.7 ± 0.6 % | **96.4 ± 0.8 %** | +0.7 |
| TCN | **95.9 ± 0.5 %** | 95.0 ± 1.0 % | −0.9 |
| LSTM (seed 13) | 94.8 % | 94.5 % | −0.3 |
| Best single model | 96.5 % (TCN s13) | **97.3 %** (Transformer s21) | |
| Best ensemble | 97.2 % | 97.2 % | 0 |

Face features help the two attention-based models by about one point on average, hurt the TCN, and
leave ensembles unchanged. With 635 test videos one video is 0.16 points; the per-architecture
differences are within about two standard deviations of the seed spread, so **the gain is small and
not established**.

### Unknown signs (part B, shipped detector)

| Model | False acceptance | False rejection |
|---|---:|---:|
| v3 BiLSTM-attention (default) | **8.8 %** | 13.2 % |
| v4 face BiLSTM-attention s7 (selected by the round) | 14.2 % | 12.8 % |

The face model misses the < 10 % target that the v3 model meets.

## Decision: the default stays the v3 model

The round's comparison step picked the face BiLSTM-attention s7 by a validation macro-F1 of
0.98103 against 0.98093 for v3. That difference is **less than one validation sequence**, and the
two validation sets differ by one sequence (272 vs 271: one recording passes the input-quality
check only in the new extraction), so it is a tie. The rule for ties, declared in v3, prefers the
smaller and cheaper model: v3 is 2.57 MB against 2.89 MB, and it does not make the browser run the
face landmarker on every frame (an extra cost on the CPU-only machines where browser accuracy is
already limited by frame rate). It is also the only one of the two that meets the unknown-sign
target.

The face model is published and can be installed instead:
[`model-bilstm_attn-20261111T053354Z-s7`](https://github.com/nvaltryek-001/ISL-NOVA/releases/tag/model-bilstm_attn-20261111T053354Z-s7)
(test top-1 95.1 %, end-to-end through the `Predictor` 95.1 %). The browser loads the face
landmarker automatically when such a model is active.

## Next

Face features may matter more for **phrases and grammar** (questions, negation) than for isolated
signs. Evaluate them again when signed sentences or new signers are available.
