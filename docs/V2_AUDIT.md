# ISL NOVA v2: audit and gap report (Phase 0)

_Branch `feat/isl-nova-v2`, created from `feat/isl-nova-platform` at `32aa056` (PR #1 still open, not merged). Audit date 2026-11-10._

Specification: [`docs/NEXT_PHASE_PROMPT.md`](NEXT_PHASE_PROMPT.md) (the only copy; there is no root-level `NEXT_PHASE_PROMPT.md`), extended by the owner's "ISL NOVA 2.0" execution prompt.

## Verified starting point

| Check | Result | Evidence |
|---|---|---|
| CI on the base branch | ✅ green | CI run 42802338321 on `32aa056` |
| pytest (SQLite) | ✅ 60 passed, 1 skipped (before v2 changes) | local run |
| Frontend unit / E2E | ✅ 17 / 19 (16 app + 3 with model) | local + CI |
| One-command install | ✅ Windows, Ubuntu, macOS | run 41977728731 |
| Model release | ✅ `model-lstm-20261104T041414Z-s13`, SHA-256 `e0979cd5…c543c0` | GitHub release |
| Dataset release | ✅ `dataset-include-landmarks-v1` (3,370 sequences) | GitHub release |
| Live demo | ✅ last verified by deploy smoke run 41861458853 (commit `d83175a`); free plan sleeps when idle | Render |

## Feature classification

| Area | Status | Notes |
|---|---|---|
| 200-slot vocabulary, verification workflow, CRUD | COMPLETED | tested (pytest + E2E) |
| English meanings | COMPLETED (source glosses) | not linguist-verified |
| Hindi / Kannada meanings | **NOT IMPLEMENTED → done in Phase 1 as drafts** | were empty `pending` |
| UI localisation (hi/kn) | **NOT IMPLEMENTED → done in Phase 1** | UI was English only |
| Speech in en-IN/hi-IN/kn-IN | COMPLETED | depends on installed browser voices |
| Live recognition (browser MediaPipe, GPU→CPU) | COMPLETED | virtual camera 74.0 % top-1 |
| LSTM / GRU / LogReg / DTW | COMPLETED | 91.7 / 86.5 / 89.1 / 84.4 % test top-1 |
| Frame-rate robustness | PARTIALLY COMPLETED | auto CPU switch exists; training ignores fps variation (Phase 2) |
| Unknown-sign rejection | PARTIALLY COMPLETED | max-softmax only; 29.3 % false acceptance (Phase 2) |
| TCN / Transformer / BiLSTM-attention | NOT IMPLEMENTED | Phase 2 |
| ONNX / in-browser model | NOT IMPLEMENTED | Phase 2 |
| Face / non-manual features | NOT IMPLEMENTED | Phase 2 (needs re-extraction) |
| Consent, recording studio, four-eyes review, dataset versions | COMPLETED | tested |
| New-signer evaluation | COMPLETED (code) · NEEDS HUMAN VALIDATION | no new-signer recordings exist |
| Real-person webcam test | NEEDS HUMAN VALIDATION | none performed |
| Practice coach, conversation mode, text→sign, PWA, teacher dashboard, gamification, analytics v2 | NOT IMPLEMENTED | Phase 4 |
| Vocabulary proposal workflow / expansion plan | PARTIALLY COMPLETED | sign CRUD exists; no proposal queue or plan |
| S3 storage, refresh tokens, password reset, 2FA, Redis, Prometheus | NOT IMPLEMENTED | Phase 6 |
| Persistent deployment | NEEDS OWNER APPROVAL | free plan resets data |
| Linguistic verification (0/200) | NEEDS HUMAN VALIDATION | qualified ISL reviewers |

## Broken items found

None in the base branch: all suites passed before changes. Known limitations are measured weaknesses, not defects (see above).

## Plan

Phases 1 → 6 in order, each tested, documented, committed and pushed. Human-dependent tasks stay marked pending. Progress and final status: [`V2_STATUS.md`](V2_STATUS.md).
