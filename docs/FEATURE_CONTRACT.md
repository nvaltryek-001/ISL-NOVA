# Feature contract `isl-nova-fc-1.0.0`

Defined in `ml/isl_nova_ml/contract.py` and implemented twice, kept equal by tests:

* Python: `ml/isl_nova_ml/features.py` (training, server inference)
* TypeScript: `frontend/src/lib/features.ts` (browser preview / quality)

`ml/tests/test_feature_parity_fixture.py` writes reference outputs. `frontend/tests/features.test.ts` asserts the TypeScript port matches them within 2×10⁻⁵ on four cases (two hands, one hand, gaps, no pose).

| Property | Value |
|---|---|
| Extractor | MediaPipe Tasks HandLandmarker (2 hands) + PoseLandmarker lite, frames **unmirrored** |
| Model input | `float32 [32, 204]` |
| Resampling | linear interpolation over frame index to 32 steps; a block is interpolated only where its source is present |
| Isotropy | x multiplied by image aspect (w/h) before any geometry |
| Body frame | origin = median shoulder midpoint, scale = median shoulder width; fallback: mean wrist and 3× median hand size |
| Missing data | zeros in the block, presence flag = 0 |
| Insufficient input | < 8 raw frames or hands in < 25 % of frames |
| Face / non-manual | **not used** in v1.0.0 (needs linguistic justification and consent review) |

| # | Block | Size | Content |
|---|---|---:|---|
| 1 | left_hand_local | 63 | 21×xyz relative to wrist, scaled by wrist→middle-MCP |
| 2 | right_hand_local | 63 | same |
| 3 | wrists_body | 6 | each wrist in body frame |
| 4 | pose_body | 27 | nose, shoulders, elbows, wrists, hips in body frame |
| 5 | two_hand | 6 | wrist-wrist distance + 5 fingertip pair distances |
| 6 | left_angles | 15 | 15 finger joint angles / π |
| 7 | right_angles | 15 | same |
| 8 | presence | 3 | left, right, pose |
| 9 | wrists_velocity | 6 | Δ wrists_body between resampled steps |

**Change rule:** any change to order, size, normalisation or sequence length bumps the version. The predictor refuses to load a model trained on a different contract version, and the parity fixture must be regenerated (`ISL_NOVA_WRITE_FIXTURE=1 pytest ml/tests/test_feature_parity_fixture.py`).

## Contract `isl-nova-fc-2.0.0` (non-manual features)

`2.0.0` = the 204 features of `1.0.0`, unchanged and in the same order, followed by a **face block of
51 values** per time step (total 255). Models record the contract they were trained with; the server
and the browser compute exactly that contract (`Predictor.features`, `extractFeaturesFor`), so 1.0.0
and 2.0.0 models can be served side by side.

| | |
|---|---|
| Landmarks | MediaPipe FaceLandmarker (478 points), 22 kept: nose tip, 3 points per eyebrow, 4 per eye, 6 mouth/lip points, chin (`contract.FACE_KEEP`). Frames carry them as `face` |
| Positions (44) | x, y of the 22 points relative to the nose tip, divided by the distance between the outer eye corners (scale- and position-invariant; aspect-corrected like the other blocks) |
| Measures (6) | mouth opening, mouth width, left/right eyebrow raise (brow to upper eyelid), left/right eye opening, all divided by the eye-corner distance |
| Presence (1) | 1 if a face was found in either neighbouring source frame |
| Missing faces | linear interpolation between present frames, else the nearest present frame, else zeros (as for hands and pose) |
| Extraction (offline) | the head is cropped from the full-resolution frame around the pose nose and upscaled to 384 px, because the face is too small for the face detector in full-body recordings (coverage on a trial part: 99.98 % of frames) |
| Browser | the camera stage loads FaceLandmarker only when the active model needs face (`/model/info → needs_face`) |
| Parity | `frontend/tests/fixtures/feature_parity_v2.json` (Python ↔ TypeScript) |
