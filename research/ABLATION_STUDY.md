# Ablation study plan

Same dataset version, split, seeds and model (LSTM baseline). Remove one block at a time by zeroing its columns at train and test time:

| Variant | Removed blocks |
|---|---|
| A0 | none (full contract) |
| A1 | left/right_hand_local |
| A2 | wrists_body, wrists_velocity |
| A3 | pose_body |
| A4 | two_hand |
| A5 | left/right_angles |
| A6 | augmentation off |
| A7 | class weighting off |
| A8 | temperature scaling off (ECE only) |

Report mean ± std of macro-F1 over ≥ 3 seeds and paired differences against A0. _Results: TBD (requires authentic data)._
