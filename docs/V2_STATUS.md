# ISL NOVA v2: status

_Branch `feat/isl-nova-v2` (from `feat/isl-nova-platform` @ `32aa056`). Updated 2026-11-10._
Every result here comes from a command that ran (local sandbox or GitHub
Actions, run linked). **Targets are listed separately from results.** Starting
audit: [V2_AUDIT.md](V2_AUDIT.md). Specification: [NEXT_PHASE_PROMPT.md](NEXT_PHASE_PROMPT.md).

Legend: ✅ done and tested · 🟡 partly done · ⏳ pending (reason given) · 👤 needs people · 💳 needs owner approval / paid resources

## Phase 0 — audit
✅ [V2_AUDIT.md](V2_AUDIT.md): base CI green, feature classification, no defects found.

## Phase 1 — 200 signs in three languages

| Item | Status | Evidence |
|---|---|---|
| English meanings for 200 signs | ✅ source glosses | `dataset/vocabulary/translations.csv` |
| Hindi + Kannada meanings for 200 signs, with transliteration | ✅ **machine drafts**, labelled `draft` / translator `machine` | `dataset/vocabulary/drafts/hi_kn_machine_drafts.csv`, `dataset/scripts/draft_translations.py` (idempotent, CI-checked) |
| Linguist verification of hi/kn | 👤 **0 / 400 verified** | needs authorised linguists; review sheet export + linguist-only import exist |
| Translation coverage, review sheet CSV, import with permission rules | ✅ | `/translations/coverage`, `/translations/review-sheet.csv`, `/translations/import`; `backend/tests/test_translations.py` |
| Interface in en / hi / kn, switcher, persisted, `<html lang>` | ✅ | `frontend/src/i18n/*`; unit test (≥ 90 % coverage, measured 100 % of titles/labels/buttons); E2E |
| Speech output in en-IN / hi-IN / kn-IN | ✅ code · depends on browser voices | — |

## Phase 2 — ML

| Item | Status | Result |
|---|---|---|
| Frame-rate / crop / missed-detection augmentation | ✅ | 3-seed test top-1 93.0 ± 0.7 % vs 90.6 ± 0.9 % ([FPS_ROBUSTNESS.md](../research/FPS_ROBUSTNESS.md)) |
| Browser accuracy (virtual camera, 73 clips) | ✅ measured · **target ≥ 85 % not met** | 83.6 % (v1 74.0 %) |
| New default model released | ✅ | `model-lstm-20261110T111537Z-s7`, 92.0 % test top-1, ECE 0.015 |
| Multi-seed runs | ✅ | 3 seeds × LSTM baseline and fps-aug; GRU fps-aug 1 seed |
| Unknown-sign detectors (maxprob, margin, entropy, centroid, combined) | ✅ compared | combined AUROC 0.932; keep-90 % FRR 10.2 % / FAR 13.7 % ([OPEN_SET_V2.md](../research/OPEN_SET_V2.md)) |
| Unknown-sign target (FAR < 10 %, FRR ≤ 15 %) | **not met** | best 12.9 % / 11.5 % |
| Combined detector inside the `Predictor` | ⏳ | measured offline only; shipped decision still uses calibrated max-probability τ |
| Explicit `__other__` class | ⏳ | next experiment in OPEN_SET_V2.md |
| TCN / Transformer / BiLSTM-attention | ⏳ not implemented | — |
| ONNX export / in-browser inference | ⏳ not implemented | — |
| Face (non-manual) features | ⏳ needs feature contract v2 and re-extraction of 56.8 GB of video | — |

## Phase 3 — real-person and new-signer evaluation

| Item | Status |
|---|---|
| New-signer evaluation workflow (`/evaluation/runs`, AI Lab) | ✅ code (from v1), tested with synthetic recordings |
| User-study protocol (consent, tasks, SUS, metrics, analysis plan) | ✅ [USER_STUDY_PROTOCOL.md](../research/USER_STUDY_PROTOCOL.md) |
| Live-webcam accuracy with real people, new-signer accuracy, user study | 👤 **not run — no participants**; no result is claimed |

## Phase 4 — product features

| Item | Status | Evidence |
|---|---|---|
| Practice Coach (reference animation, scored attempt, per-part tips) | ✅ | references from INCLUDE train split (release `references-v1`); pytest + E2E; similarity own vs other median 93 vs 13 on 120 test recordings |
| Text-to-Sign (English / Hindi words → reference animations) | ✅ | E2E |
| Conversation mode (speech-to-text ↔ continuous sign recognition) | ✅ code · speech recognition depends on the browser; not testable headless | page E2E (h1/a11y) |
| Continuous phrase recognition | 🟡 sliding-window recognition with de-duplication, shown as a *recognized word sequence* (not a translation); no trained segmentation model | — |
| Installable PWA, offline shell, offline badge | ✅ | E2E |
| Teacher dashboard | ⏳ not implemented | — |
| Gamification: streaks, points, weekly goal, 7 badges — computed only from the learner's own attempts; Practice Coach attempts count (score ≥ 70 = pass) | ✅ | `/learning/achievements`; pytest + E2E |
| Analytics v2 | ⏳ not implemented (Prometheus metrics cover service analytics) | — |

## Phase 5 — toward 500 signs

| Item | Status |
|---|---|
| Expansion plan (sources, licences, review gates, data targets) | ✅ [dataset/EXPANSION_PLAN.md](../dataset/EXPANSION_PLAN.md) |
| Vocabulary proposals with duplicate prevention; linguist accept/reject; accepted signs get ISL201+ ids and hi/kn drafts | ✅ pytest |
| Actual new signs, recordings and models beyond 200 | 👤 needs licensed sources, signers and linguists |

## Phase 6 — platform

| Item | Status | Evidence |
|---|---|---|
| Prometheus `/metrics` (requests, latency, predictions by state) | ✅ | pytest |
| Sign out everywhere (token versioning) | ✅ | pytest + E2E |
| Password reset (admin-issued one-time codes; no email service) | ✅ | pytest + E2E |
| TOTP two-factor sign-in (RFC 6238, replay-protected) | ✅ | RFC test vectors, pytest + E2E |
| Data-retention job (scheduled, CLI, admin endpoint; recordings only reported) | ✅ | pytest |
| Automated accessibility scan (axe-core, WCAG 2.1 A/AA, 18 routes × 2 themes) | ✅ 0 serious/critical after fixing 4 issue types | CI |
| Dependency audit | ✅ CI `audit` job (pip-audit, npm audit) | CI |
| Refresh tokens | ⏳ not implemented (access tokens + sign-out-everywhere instead) | — |
| Email-based password reset | ⏳ needs an email provider 💳 | — |
| S3 / MinIO object storage | ⏳ not implemented (local storage abstraction exists) | — |
| Redis rate limiting / job queue | ⏳ not implemented (in-process limiter and job runner) | — |
| Load test | ⏳ not run | — |
| Persistent deployment (database + disk that survive restarts) | 💳 needs owner approval for a paid plan; the free demo still runs v1 | — |
| v2 deployed | ⏳ not deployed: the Render service tracks `feat/isl-nova-platform`; switching it needs the owner's go-ahead | — |

## Additional upgrades (A–F)

| | Upgrade | Status |
|---|---|---|
| A | UI/UX: language switcher, online/offline badge, new navigation, contrast fixes | ✅ |
| B | Recognition UX: decision states, top-5, Practice Coach feedback, Conversation | ✅ |
| C | Feedback / corrections | ✅ from v1 (corrections in history, feedback inbox) |
| D | Vocabulary / learning quality: three-language meanings, proposals, review sheet | ✅ (verification 👤) |
| E | Privacy: retention job, sign-out-everywhere, 2FA, PWA never caches API data | ✅ |
| F | Reliability: CI on SQLite + PostgreSQL, a11y scan, installers on 3 OSes | ✅ |

## Human-dependent tasks (still pending)

1. Linguist review of 200 English glosses and 400 Hindi/Kannada drafts.
2. Live-webcam and new-signer recordings under the consent workflow, then the new-signer evaluation.
3. User study per the protocol.
4. Owner decisions: paid persistent hosting; deploying v2; merging PR #1 and the v2 PR.
