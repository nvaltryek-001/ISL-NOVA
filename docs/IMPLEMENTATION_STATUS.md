# Implementation status

_Last updated: 2026-11-04, branch `feat/isl-nova-platform`._ Every result below
was produced by a command that actually ran: in the build sandbox (2 vCPU,
Python 3.13, Node 22, Chromium via Playwright), in GitHub Actions, or against
the live deployment. **Implemented** and **tested** are reported separately.

## Implemented vs tested

| Capability | Implemented | Tested | Evidence / result |
|---|:---:|:---:|---|
| 200 vocabulary slots ISL001–ISL200, sources, states | ✅ | ✅ | vocabulary build reproducible; tests |
| INCLUDE download + landmark extraction | ✅ | ✅ | run [41764539272](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41764539272): 44/44 parts, 56.75 GB MD5-verified, 3,370 usable sequences, 0 failed |
| Out-of-vocabulary extraction (open set) | ✅ | ✅ | run [41773683352](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41773683352): 887 sequences, 62 reserve glosses |
| Training (LSTM, GRU, LogReg, DTW) on 200 classes | ✅ | ✅ | run [41771084083](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41771084083): LSTM 91.7 % top-1 / 98.3 % top-5 / 91.7 % macro-F1 (official split, not signer-independent) |
| Production `Predictor` on the test split | ✅ | ✅ | 635 sequences, 91.65 % top-1 reproduced |
| Unknown-sign detection | ✅ | ✅ | run [41815223675](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41815223675): AUROC 0.900; **29.3 % of unknown sequences recognized** at τ; 84.4 % of known recognized and correct |
| Raw video → Python MediaPipe → model | ✅ | ✅ | 67 / 73 held-out test videos top-1 correct |
| In-browser MediaPipe in CI Chromium | ✅ | ✅ | run [41815175935](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41815175935): bundle 52–85 ms, hand model GPU 0.2–0.7 s / CPU 0.4 s, UI ready in 10 s |
| Browser capture on held-out video (virtual camera) | ✅ | LIVEEVAL_STATUS | LIVEEVAL_EVIDENCE |
| Live webcam with a real person | ✅ | ⛔ | not tested: no camera or person in any build environment |
| New-signer evaluation (`/evaluation/runs`, AI Lab tab) | ✅ | ✅ code path | synthetic recordings only; **no new-signer data, no accuracy figure** |
| Vocabulary verification (checklist, documented entry, review sheet) | ✅ | ✅ | API tests + E2E; **0 / 200 verified**, no approvals made ([protocol](VERIFICATION_PROTOCOL.md)) |
| RBAC, consent, four-eyes review, erasure, audit | ✅ | ✅ | pytest on SQLite and PostgreSQL 16; E2E |
| Responsive layout + accessibility basics | ✅ | ✅ | E2E: 11 routes at 360 / 768 / 1280 px and with a wide fallback font; labels, alt, link names, landmarks |
| Security headers, CSP, HSTS (production) | ✅ | ✅ | `test_security_headers_and_cors`; deployed headers checked by smoke test |
| Dependency audit | ✅ | ✅ | CI `audit` job: pip-audit **no known vulnerabilities**; npm audit found GHSA-mrhx-c7xc-m3w5 (zod, high), fixed by removing zod |
| Windows local setup | ✅ | ✅ | [run 41842534266](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41842534266) on `windows-latest`, Windows PowerShell 5.1: `setup_windows.ps1` → `start_windows.ps1` → 24/24 held-out samples through the local API → `test_windows.ps1 -E2E -WithModel`: ruff, 60 pytest, 16 unit, **19/19 E2E** |
| Free-tier deployment with the model installed | ✅ | ✅ | [isl-nova.onrender.com](https://isl-nova.onrender.com): `/health` ok, `/model/info` = `lstm-20261104T041414Z-s13`, 200 classes, `synthetic: false`; deploy smoke [run 41817628215](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41817628215): 24/24 held-out samples correct and *recognized* through the public API (median round trip 497 ms, US runner → Singapore), MediaPipe loads on GPU in the deployed UI at 1280 and 390 px |

## Test suites (latest)

| Check | Command | Result |
|---|---|---|
| Python lint | `ruff check backend ml dataset/scripts scripts` | ✅ pass |
| Backend + ML (SQLite) | `pytest -q` | ✅ **60 passed, 1 skipped** (needs a MediaPipe `.task` file offline) |
| Backend (PostgreSQL 16) | CI service container | ✅ pass |
| Frontend type check | `tsc --noEmit` (strict) | ✅ pass |
| Frontend unit + feature parity | `npm test` | ✅ 17 passed |
| End-to-end | `npm run e2e` with `E2E_MODEL_TAG` | ✅ **19 passed** (CI [41815644645](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41815644645)) |
| Docker build + container health | CI `docker` job | ✅ pass |

## Bugs found by tests and evaluation runs, and fixed

* **Video upload failed on Windows.** `probe_video` kept a `NamedTemporaryFile` open while OpenCV opened it by name, which Windows does not allow, so every upload was rejected as undecodable. Found by the Windows E2E run; now uses a closed temp file.
* **Virtual-camera evaluation: relative video path.** Chromium's `--use-file-for-fake-video-capture` needs an absolute path; with a relative one the page showed *Camera unavailable: Requested device not found* for every clip. Found with page-state diagnostics added to the harness.
* **Silent empty capture.** If no frames were processed during a capture, the Live page returned to idle without any message. It now answers *insufficient input* with a reason.
* **E2E race on fast machines.** The live-studio test read the extractor state and the button state separately; on the Windows runner MediaPipe finished loading in between. Now one snapshot.

* **Virtual-camera evaluation never reached MediaPipe.** The script did not grant camera permission and Playwright denies ungranted permissions, so all 73 clips timed out. A diagnostic workflow showed that MediaPipe itself loads in under a second. Fixed by granting the permission.
* **/dataset overflowed by 7 px at 360 px on CI only.** The runner's fallback font is wider. The cause was a `Card` header that could not wrap its filter control. Card and page headers now wrap, and the E2E pass repeats with a wide font.
* **API docs page was blank under its own CSP.** It used an inline script and an unpinned CDN version. The init script is now served same-origin and Swagger UI is pinned.
* Earlier: PostgreSQL FK order on signer erasure; `Decimal` from PostgreSQL `SUM()`; a synthetic class id written into a vocabulary FK; dialog accessible names; 38 px mobile header overflow; Tailwind tokenizer on arbitrary values; unchecked consent retention; DTW memory blow-up; non-monotonic MediaPipe timestamps across videos; INCLUDE file-name matching.

## Numbers that matter

| Metric | Value |
|---|---:|
| Class slots | 200 |
| Linguistically verified | **0** |
| Classes trained / evaluated on INCLUDE | 200 / 200 (189 with samples in all splits) |
| Test top-1 / top-5 / macro-F1 (LSTM) | 91.7 % / 98.3 % / 91.7 % |
| Unknown-sign AUROC / false recognition at τ | 0.900 / 29.3 % |
| New-signer accuracy | not measured (no data) |
| Live-person webcam accuracy | not measured |

## What remains (needs people or data, not code)

1. Qualified ISL reviewers (Deaf signers or accredited interpreters) to verify the 200 signs with the checklist.
2. Consented recordings from signers outside INCLUDE, to run the new-signer evaluation.
3. A real-person webcam study, with consent and a written protocol.
4. A stronger unknown-sign detector (energy score, background class, or embedding distance).
5. Owner approval for a persistent deployment (disk or managed PostgreSQL) if the demo should keep data.
