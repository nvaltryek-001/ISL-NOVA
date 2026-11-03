# Implementation status

_Last updated: 2026-11-03, branch `feat/isl-nova-platform`._ Every result below was produced by a command that actually ran in the build sandbox (2 vCPU, Python 3.13.18, Node 22.23.4, Chromium via Playwright 1.63).

## Verification evidence

| Check | Command | Result |
|---|---|---|
| Python lint | `ruff check backend ml dataset/scripts scripts` | ✅ all checks passed |
| Backend + ML tests (SQLite) | `pytest -q` | ✅ **56 passed, 1 skipped**. The skip is `test_extractor_runs_on_a_video`, which needs a MediaPipe `.task` model file that is not available offline. |
| Backend tests (PostgreSQL) | `TEST_DATABASE_URL=… pytest backend/tests` (GitHub Actions, PostgreSQL 16 service) | ✅ passed in CI run 41678896858 (the first CI run found a real FK-order bug, now fixed) |
| PostgreSQL schema | rendered DDL applied to PostgreSQL 16.15 with `ON_ERROR_STOP=1` | ✅ 28 tables created |
| PostgreSQL query compatibility | every distinct SQL statement executed by the test suite (163) run through `PREPARE` on PostgreSQL 16.15 | ✅ 0 errors |
| Vocabulary reproducibility | `python dataset/scripts/build_vocabulary.py` then diff | ✅ identical output |
| Frontend type check | `tsc --noEmit` (strict) | ✅ exit 0 |
| Frontend unit tests | `npm test` | ✅ **16 passed** (includes 4 Python↔TypeScript feature-parity cases, max diff < 2×10⁻⁵) |
| Production build | `npm run build` | ✅ JS 405 kB, CSS 49 kB (minified, before gzip) |
| End-to-end (Chromium, fake camera) | `npm run e2e` | ✅ **15 passed** (4 consecutive clean runs after the light-theme redesign); screenshot run (`E2E_SCREENSHOTS=1`) also passed |
| Synthetic ML smoke test | `python -m isl_nova_ml.smoke` | ✅ all 4 model kinds train, calibrate, evaluate and register. **Metrics are synthetic and are not ISL results.** |
| Docker image build + container health | `docker build .` and `/api/v1/health` (GitHub Actions) | ✅ passed in CI run 41678896858 (not buildable in the sandbox) |
| Container layout + production start | files copied as in the Dockerfile; `ISL_NOVA_ENV=production` migrate + uvicorn | ✅ health ok, SPA served, 200 slots seeded; refuses to start without `JWT_SECRET` |
| Deployment | - | ⛔ not deployed (no credentials) |

### Bugs found by the tests and fixed
* Flaky review-workflow E2E check read stats before the verification dialog closed; now waits for the post-verification state.
* **PostgreSQL only (found by CI):** erasing a signer violated the recordings → consent FK because PostgreSQL checks it before cascading. Fixed by deleting in explicit dependency order.
* CI E2E flake: recording took longer than 15 s when MediaPipe really loaded on the runner; timeouts raised.
* A synthetic class ID was written into the `recognition_history.chosen_sign` foreign key, causing an integrity error. Fixed by only storing vocabulary IDs.
* PostgreSQL `SUM()` returns `Decimal`, which breaks JSON responses. Values are now normalised in `db.py`.
* Dialog `aria-labelledby` used titles containing spaces, which broke the accessible name. Now uses `useId()`.
* Mobile header overflowed by 38 px. The search button lacked `min-w-0`.
* The Tailwind candidate tokenizer split arbitrary values such as `grid-cols-[minmax(0,1fr)_…]`.
* Expired consent retention was documented but not checked; `dataset/validate` now flags it (with a test).

## Specification acceptance criteria

| Area | Criterion | Status |
|---|---|---|
| Dataset | exactly 200 stable IDs | ✅ ISL001–ISL200 |
| | every entry has verification and readiness state | ✅ |
| | no invented signs or translations | ✅ Hindi/Kannada left pending; glosses from source |
| | sources and licences traceable | ✅ `references.csv`, `sign_references` |
| | consent/review workflow works | ✅ E2E: signer → consent → record → annotate → second-reviewer approval |
| | manifests validate; actual counts shown | ✅ |
| AI | versioned feature contract; train/infer parity | ✅ |
| | genuine model artefacts load; inference tested | ⚠️ loading and inference tested with a **synthetic** model only; **no genuine model exists** |
| | unknown/uncertain handling | ✅ |
| | metrics from held-out evaluation; no fabricated accuracy | ✅ pipeline evaluates test once; no ISL metrics claimed |
| Product | core routes work, no dead buttons, responsive, loading/error/empty states, server-side permissions | ✅ (E2E covers all routes, 390 px layout, unnamed-button check) |
| Quality | tests run; production build; security addressed | ✅ |
| | Docker path verified | ✅ image built and health-checked in CI |
| Delivery | README, docs, branch pushed | ✅ |
| | PR / deployment | ✅ PR #1 opened · ⛔ no deployment credentials |

## 200-class dataset numbers
| Metric | Value |
|---|---:|
| Class slots | 200 |
| Linguistically verified | 0 |
| Classes with authentic local recordings | 0 |
| Classes approved for training | 0 |
| Classes used for training / evaluated | 0 / 0 |
| External videos listed (INCLUDE, not downloaded) | 3,392 |

## Continuation notes
1. Review and merge PR #1 (CI green).
2. Download INCLUDE plus the MediaPipe task files, run `include_import`, train `ml/configs/lstm_baseline.json`, and fill [MODEL_CARD.md](MODEL_CARD.md) from `metrics.json`.
3. Assign the `linguist` role only to qualified ISL reviewers and start verification of the 200 slots.
4. Choose a licence for the project (none is committed; see README).
