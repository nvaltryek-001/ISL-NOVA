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
