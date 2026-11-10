# Frame-rate robustness (ISL NOVA v2, Phase 2a)

**Question.** The browser pipeline gave 74.0 % top-1 on held-out clips against
91.8 % offline, mostly because in-browser MediaPipe ran at ~10 fps on a CPU-only
runner while the training videos are 25 fps. Does training on landmark sequences
that simulate low and uneven frame rates close that gap?

## Method

`ml/isl_nova_ml/augment.py · raw_variant()` creates extra training sequences
from the **raw landmarks** before the feature contract is applied:

* resample from 25 fps to a random rate in **8–30 fps** (with jitter on frame times),
* random temporal crop of up to **15 %** at the start and end,
* drop hand detections on up to **15 %** of frames (as MediaPipe does on blur).

`raw_aug_copies: 4` adds four such variants per training sequence (training split
only; validation and test are untouched). Configs: `ml/configs/lstm_fps_aug.json`,
`ml/configs/gru_fps_aug.json`. Same data (`include-official-v1`), split, features
(`isl-nova-fc-1.0.0`) and selection rule (validation macro-F1) as v1.

Training run: [42804474143](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42804474143) (matrix from `ml/runs/include-train.json`).

## Held-out test split (635 sequences, evaluated once per model)

| Model | Seed | Test top-1 | Test top-5 | Test macro-F1 |
|---|---:|---:|---:|---:|
| LSTM baseline | 13 (v1 release) | 91.7 % | 98.3 % | 91.7 % |
| LSTM baseline | 7 | 89.6 % | — | 88.8 % |
| LSTM baseline | 21 | 90.4 % | — | 90.4 % |
| **LSTM + fps augmentation** | **7 (released v2)** | **92.0 %** | **98.7 %** | **91.6 %** |
| LSTM + fps augmentation | 13 | 93.5 % | 99.1 % | 93.5 % |
| LSTM + fps augmentation | 21 | 93.5 % | 99.1 % | 93.1 % |
| GRU + fps augmentation | 13 | 93.2 % | — | 93.3 % |

| Mean ± std over 3 seeds | Top-1 | Macro-F1 |
|---|---:|---:|
| LSTM baseline (s7, s13, s21) | 90.6 ± 0.9 % | 90.3 ± 1.2 % |
| LSTM + fps augmentation (s7, s13, s21) | **93.0 ± 0.7 %** | **92.7 ± 0.8 %** |

The fps-augmented GRU (93.2 %) compares with 86.5 % for the v1 GRU (single seed).
The released v2 model is seed 7, **chosen by validation macro-F1 (95.8 %)**, not
by test score — seeds 13 and 21 scored higher on test, which is why the choice
rule matters. ECE 0.015; the production `Predictor` reproduces 91.97 % top-1 on
all 635 test sequences.

## Through the browser (virtual camera)

Same 73 held-out INCLUDE test clips (Greetings, Seasons, Colours) played into
headless Chromium as its webcam and recognised through the real Live page, with
in-browser MediaPipe on the CPU delegate:

| | v1 model `…041414Z-s13` ([run 41860050670](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41860050670)) | v2 model `…111537Z-s7` ([run 42807661120](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42807661120)) |
|---|---:|---:|
| Clips completed | 73 / 73 | 73 / 73 |
| **Browser top-1** | 74.0 % (54) | **83.6 % (61)** |
| Browser top-5 | 89.0 % | **97.3 %** |
| *recognized* answers that were correct | 45 / 48 (93.8 %) | 49 / 54 (90.7 %) |
| States | 48 recognized · 17 uncertain · 8 unknown | 54 recognized · 14 uncertain · 5 unknown |
| Offline Python on the same clips | 91.8 % | 89.0 % |
| Gap browser vs offline | 17.8 points | **5.5 points** |
| Hand tracking at capture | ~10 fps, CPU | median 9 fps, CPU |

## Verdict against the v2 target

| Target | Result | Status |
|---|---|---|
| Browser top-1 ≥ 85 % on the virtual-camera clips | 83.6 % | **Not met** (closer: +9.6 points) |
| No loss on the held-out test split | 92.0 % vs 91.7 % (3-seed means 93.0 vs 90.6 %) | Met |
| Results over ≥ 3 seeds | 3 seeds per LSTM variant | Met |

## Caveats

* Same signers as training (INCLUDE has no signer IDs) — **not signer-independent**.
* 73 clips from three categories: a ±5-point difference is within noise
  (one clip = 1.4 points).
* A replay of recordings, **not a live person in front of a webcam**.
* Unknown-sign behaviour changed too: better separation (AUROC 0.918 vs 0.900),
  but at the validation-chosen τ more unknown signs are *recognized*
  (34.0 % vs 29.3 %). See [OPEN_SET_V2.md](OPEN_SET_V2.md).
