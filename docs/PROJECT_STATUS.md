# ISL NOVA: project status

_Branch `main`. Updated 2026-11-10._ Scope: **200 signs** (`ISL001`–`ISL200`) in **English, Hindi
and Kannada**; the vocabulary is fixed (`VOCABULARY_LIMIT=200`). Every result below was produced by
a command that ran (GitHub Actions run or local test, linked). Targets are listed separately from
results. Earlier detail: [V2_AUDIT.md](V2_AUDIT.md), [V2_STATUS.md](V2_STATUS.md).

Legend: ✅ done and tested · ⚠️ done, target not met · 👤 needs people · 💳 needs the owner's approval or money

## Remaining-work phases (7–11), all done in code

| Phase | Item | Status | Evidence |
|---|---|---|---|
| 7 | Combined unknown-sign detector inside the app (server **and** on-device) | ✅ | `open_set_detector` in `model.json`; `Predictor.state_for`; `webModel.ts` |
| 7 | Explicit "other / not a sign" class | ✅ tried | trained on unknown part A1; part-B FAR 16–25 %, not better than the detector ([V3_MODELS.md](../research/V3_MODELS.md)) |
| 7 | Better threshold: FAR < 10 %, FRR ≤ 15 % | ✅ **met** | part B: **FAR 8.8 %, FRR 13.2 %** ([run 42851786127](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42851786127)) |
| 7 | Re-run evaluations | ✅ | open-set v3, detector comparison, Predictor end-to-end 95.12 % |
| 8 | Transformer, TCN, BiLSTM-attention, 3 seeds each | ✅ | 15 trained models; gradient checks in `ml/tests/test_deep.py` |
| 8 | Ensembles | ✅ | 5 ensembles, 96.5–97.2 % test top-1 (not selected: validation tie, see V3_MODELS.md) |
| 8 | Browser accuracy ≥ 85 % | ⚠️ **not met** (by one clip) | **84.9 %** (62/73 held-out clips through the Live page; v2 83.6 %, v1 74.0 %); 49/50 *recognized* answers correct; [run 42859291767](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42859291767) |
| 8 | Weakest signs | ✅ improved overall | test macro-F1 91.6 % → 94.1 %; per-class F1 in the release `metrics.json` |
| 8 | ONNX export | ✅ | `export_web --onnx` (LSTM), onnxruntime parity test in CI |
| 8 | Model in the browser | ✅ | TypeScript runtime for LSTM, GRU, BiLSTM-attention; matches Python to 1e-8; 24/24 agreement in E2E |
| 8 | Face (non-manual) features | ⏳ not done | needs feature contract v2 and re-extraction of the 56.8 GB INCLUDE videos (several hours of runner time) |
| 9 | Teacher dashboard (classes, join codes, progress, hard signs) | ✅ | pytest + E2E |
| 9 | Analytics v2 | ✅ | pytest + E2E |
| 9 | Phrase recognition: signs split at pauses | ✅ | `SignSegmenter` unit tests; Conversation page; shown as a *recognized word sequence* |
| 9 | Review reminders (spaced repetition) and daily goal | ✅ | pytest + E2E |
| 10 | Refresh tokens (rotation, reuse detection, logout) | ✅ | pytest + E2E |
| 10 | S3-compatible storage | ✅ | CI against a real S3 server (SeaweedFS with SigV4 checks) |
| 10 | Redis rate limit + job queue + worker | ✅ | CI against real Redis; worker end-to-end test |
| 10 | Load test | ✅ | ~90 req/s on 2 vCPU, 0 errors ([LOAD_TEST.md](LOAD_TEST.md)) |
| 10 | Grafana dashboard | ✅ | `monitoring/`; test checks its queries against the app's metrics |
| 11 | README, model card, results, report chapter 11 | ✅ | this commit |
| 11 | Install checks | ✅ Windows + Ubuntu | runs [42859318362](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42859318362), [42859313452](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42859313452); macOS job cancelled by GitHub before start (no runner) |
| 11 | Release v2.0.0 | ✅ | [release v2.0.0](https://github.com/nvaltryek-001/ISL-NOVA/releases/tag/v2.0.0) (tag created by the release workflow) |
| 11 | Update the live demo | 💳 | needs the owner's go-ahead; the demo still runs v1 |

## Needs people (not done, no results claimed)

1. ISL experts verify the 200 signs (0 / 200 verified).
2. Language experts check the 400 Hindi and Kannada meanings (all machine drafts).
3. A real person tests recognition at a webcam.
4. New signers recorded with consent; accuracy on new signers (the tool is ready).
5. A user study with Deaf users ([protocol](../research/USER_STUDY_PROTOCOL.md)).

## Needs the owner's decision

1. Deploy `main` to the free demo (switch the Render service to `main` and set
   `ISL_NOVA_MODEL_TAG=model-bilstm_attn-20261110T162800Z-s7`).
2. Paid hosting for data that survives restarts; an email provider for password reset by email.
3. Change the local admin password that was published in an old README commit.
