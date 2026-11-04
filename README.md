<div align="center">

<img src="frontend/public/favicon.svg" alt="ISL NOVA logo" width="88" />

# ISL NOVA

### Beyond Gestures. Towards Understanding.

An open, consent-first platform for **Indian Sign Language** recognition, learning and dataset building, honest about what it can and cannot do yet.

[![CI](https://github.com/nvaltryek-001/ISL-NOVA/actions/workflows/ci.yml/badge.svg?branch=feat%2Fisl-nova-platform)](https://github.com/nvaltryek-001/ISL-NOVA/actions/workflows/ci.yml)
![version](https://img.shields.io/badge/version-0.1.0-8b5cf6)
![python](https://img.shields.io/badge/python-3.13-3776ab)
![react](https://img.shields.io/badge/react-19.2-22d3ee)
![model](https://img.shields.io/badge/LSTM%20(INCLUDE%20test)-91.7%25%20top--1%20·%20200%20classes-10b981)
![open-set](https://img.shields.io/badge/unknown--sign%20AUROC-0.900-f59e0b)
[![demo](https://img.shields.io/badge/live%20demo-isl--nova.onrender.com-8b5cf6)](https://isl-nova.onrender.com)

<p>
  <a href="https://isl-nova.onrender.com"><b>Live demo</b></a> ·
  <a href="#-results">Results</a> ·
  <a href="#-implemented-vs-tested">What is tested</a> ·
  <a href="docs/MODEL_CARD.md">Model card</a> ·
  <a href="#-quick-start">Quick start</a>
</p>

</div>

> [!IMPORTANT]
> **Project status, stated plainly.**
> * ✅ **Platform built and tested:** 200 vocabulary slots, the consent-first data pipeline, training and evaluation, webcam recognition, and every application module. CI is green: 60 Python tests, 16 unit tests, 19 end-to-end tests.
> * ✅ **Real model:** an LSTM trained on genuine INCLUDE recordings covers all **200 classes**. On the 635-video official test split it scores **91.7 % top-1, 98.3 % top-5 and 91.7 % macro-F1**.
> * ✅ **Deployed:** a free-tier demo with that model installed runs at **[isl-nova.onrender.com](https://isl-nova.onrender.com)**.
> * ⚠️ **Unknown signs:** tested on 62 held-out INCLUDE glosses, rejection is **weak**. AUROC is 0.900, but **29 % of unseen signs are still "recognized"** as a vocabulary sign.
> * ⛔ **Not yet shown:** accuracy on new signers (INCLUDE has no signer IDs, so these results are **not signer-independent**); recognition with a real person in front of a webcam; and linguistic verification. **0 of 200 signs are verified.**

<p align="center">
  <img src="docs/screenshots/dashboard.png" alt="ISL NOVA dashboard showing 200 class slots, 0 verified, no trained model" width="100%" />
</p>

## Contents
- [Why ISL NOVA](#-why-isl-nova)
- [Features](#-features)
- [Architecture](#-architecture)
- [Screenshots](#-screenshots)
- [Quick start](#-quick-start)
- [The 200-class dataset](#-the-200-class-dataset)
- [Train a model](#-train-a-model)
- [Results](#-results)
- [Implemented vs tested](#-implemented-vs-tested)
- [Live demo](#-live-demo)
- [API](#-api)
- [Testing](#-testing)
- [Deployment](#-deployment)
- [Research](#-research)
- [Privacy and data governance](#-privacy-and-data-governance)
- [Limitations](#-limitations)
- [Repository structure](#-repository-structure)
- [Contributing](#-contributing) · [Licence and attribution](#-licence-and-attribution) · [Roadmap](#-roadmap) · [References](#-references)

## 💡 Why ISL NOVA

Indian Sign Language has few openly licensed, consented datasets. Many recognition demos report accuracy on the same signers they trained on. ISL NOVA is designed around three things that are usually missing:

1. **Traceability.** Every vocabulary entry has a licensed source, a verification state and a data-readiness state. They are reported separately, so "200 classes" never silently means "200 trained classes".
2. **Consent.** Recording is impossible without an informed-consent record. Training is impossible without `model_training` consent. Withdrawing consent erases media.
3. **Honest evaluation.** Signer-independent splits, leakage checks, calibrated confidence, and explicit *uncertain* and *unknown* answers.

## ✨ Features

| Module | What it does |
|---|---|
| **NOVA Core** | Accounts, PBKDF2 + JWT auth, five roles with server-side RBAC, profile, notifications, audit log, health endpoint |
| **Dashboard** | Live counts from the database and registry: slots, verified signs, recordings, training-ready classes, model status, system health |
| **Live Recognition Studio** | Webcam with camera selection, in-browser MediaPipe hand + pose landmarks and overlay, *capture one sign* or continuous sliding window, top-5 with smoothing, adjustable capture length (1.5 / 2.5 / 3.5 s) with optional countdown, GPU→CPU fallback with a live fps badge, states `recognized · uncertain · unknown · insufficient_input · model_unavailable · camera_unavailable`, meanings in en/hi/kn, speech, copy, save, correction reports. **Video never leaves the device.** |
| **Video Analysis** | Validated upload (magic bytes, decode, size), background job, hand-tracking timeline, windowed inference when a model exists, JSON export, 24-hour auto-deletion |
| **Sign Explorer** | Multilingual search, category/status filters, sign detail with licensed references, review log, related signs, bookmarks, correction reports; reviewers get **full CRUD** (create, edit, retire/restore, references, translations); linguists verify with a **required three-item checklist** and can export a CSV **review sheet** for all 200 signs |
| **Communication Workspace** | Word-by-word composer from sign meanings, editable text, speech, copy/share, saved phrases. It is clearly labelled as *not* an ISL translator. |
| **Learning Academy** | Lessons by category, quizzes built **only from verified signs and verified meanings**, progress and "review these signs" |
| **Dataset Intelligence Lab** | Readiness funnel and per-class table, pseudonymous signers, consent scopes and withdrawal, sessions, **Recording Studio** (countdown, MediaRecorder + landmarks, quality badges), four-eyes review queue, validation, immutable versioned manifests |
| **AI Laboratory** | Active model, held-out metrics, per-class report and confusion matrix, model registry with promote/rollback, experiments run as background jobs, **new-signer evaluation runs** (overall + per signer), feature-contract viewer |
| **Research Centre** | Research questions, evidence status, protocol documents, verified references, intentionally empty results table |
| **3D Visualisation** *(experimental)* | Record or load real landmark sequences; orbit, frame stepping, speed, wrist trajectories |
| **Admin & Kiosk** | User roles, feedback inbox, audit log; full-screen high-contrast kiosk with large targets, verified quick phrases and one-tap session reset |

**Design:** a clean **light theme by default** (white cards on a soft violet-tinted canvas, deep-violet accents, AA-contrast status colours) with a one-click **dark theme** toggle in the header, or *match my device* in Settings. Both themes share one token system (`frontend/src/styles.css`).

Accessibility throughout: keyboard navigation and visible focus, skip link, labelled controls, high-contrast, reduced-motion and large-text modes, and a responsive layout checked by E2E on 11 routes at 360, 768 and 1280 px (including a wide fallback font), with automated checks for labelled controls, image alt text, link names and landmarks.

## 🏗 Architecture

```mermaid
flowchart LR
  subgraph Browser["Browser (React 19 + TypeScript + Tailwind v4)"]
    CAM[Webcam] --> MP[MediaPipe Tasks<br/>hands + pose]
    MP --> UI[ISL NOVA UI]
  end
  UI -- "landmarks (JSON), never video" --> API
  subgraph Server["Python modular monolith (Starlette + Pydantic)"]
    API[/api/v1/] --> RBAC[Auth · RBAC · rate limits · audit]
    API --> FC[Feature contract<br/>isl-nova-fc-1.0.0]
    FC --> PRED[Calibrated predictor<br/>τ + margin → state]
    API --> JOBS[Background jobs]
    JOBS --> TRAIN[Training pipeline<br/>LSTM · GRU · LogReg · DTW]
    TRAIN --> REG[(Model registry<br/>checksummed)]
    PRED --> REG
  end
  API --> DB[(PostgreSQL 16)]
  API --> OBJ[(Object storage)]
  INC[(INCLUDE · CC BY 4.0)] -. importer .-> OBJ
```

| Layer | Technology |
|---|---|
| Frontend | React 19.2, TypeScript 6 (strict), Tailwind CSS 4.3, esbuild 0.28, Zod, in-house router / query cache / store, SVG charts |
| Backend | Python 3.13, Starlette 1.7, Pydantic 2.13, PyJWT, versioned SQL migrations, structured JSON logs |
| Data | PostgreSQL 16 (production), SQLite (development), local object-storage adapter |
| CV / ML | MediaPipe Tasks, OpenCV 5, NumPy (LSTM/GRU with gradient-checked backprop), scikit-learn |
| Quality | pytest, node:test, Playwright E2E, Ruff, GitHub Actions, Docker |

Why Starlette rather than FastAPI, and esbuild rather than Vite? The build environment had no package-registry access, so the project uses the tested foundations of those tools. See [docs/TECH_STACK.md](docs/TECH_STACK.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## 📸 Screenshots

All screenshots were captured by Playwright from the running application, on a local test database.

<p align="center"><img src="docs/screenshots/dashboard-model.png" alt="Dashboard with the trained 200-class model live" width="100%" /></p>

| | |
|---|---|
| ![AI Laboratory with the trained LSTM's held-out metrics](docs/screenshots/ai-laboratory-model.png) **AI Laboratory.** Held-out metrics, read from the model's own `metrics.json`. | ![Per-class F1 and 200-class confusion matrix](docs/screenshots/evaluation.png) **Evaluation.** Per-class F1 and the 200 × 200 confusion matrix. |
| ![Verification dialog with the three-item checklist](docs/screenshots/verification-checklist.png) **Verification.** The reviewer must document the sign and tick all three checks; Confirm stays disabled until they do. | ![New-signer evaluation tab](docs/screenshots/ai-laboratory-new-signers.png) **New signers.** Evaluate the live model on consented recordings from people outside INCLUDE (no such data yet). |
| ![Sign detail with licensed reference and review workflow](docs/screenshots/sign-detail.png) **Sign detail.** Licensed source, pending meanings, review log. | ![Dataset Lab readiness funnel](docs/screenshots/dataset-lab.png) **Dataset Lab.** Readiness funnel and per-class table. |
| ![Communication composer](docs/screenshots/communication.png) **Communication.** Composer with unverified-meaning warnings. | ![Kiosk mode](docs/screenshots/kiosk.png) **Kiosk.** High contrast, large targets. |

<details><summary>More: dark theme · Live Recognition · Sign Explorer · mobile</summary>

<img src="docs/screenshots/dashboard-dark.png" alt="Dashboard in dark theme" width="100%" />

<img src="docs/screenshots/live-recognition.png" alt="Live recognition before a model is installed" width="49%" /> <img src="docs/screenshots/sign-explorer.png" alt="Sign explorer grid" width="49%" />

<img src="docs/screenshots/mobile-dashboard.png" alt="Mobile dashboard" width="30%" /> <img src="docs/screenshots/mobile-dataset.png" alt="Mobile Dataset Lab at 360 px" width="30%" />

The Live Recognition capture shows the state before a model was installed. In the offline build sandbox MediaPipe could not load from its CDN, and the page says so.
</details>

## 🚀 Quick start

**Requirements:** Python 3.11+ (tested 3.13), Node 22, a modern Chromium/Firefox/Safari for the camera.

```bash
git clone https://github.com/nvaltryek-001/ISL-NOVA.git && cd ISL-NOVA
git checkout feat/isl-nova-platform

# backend
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-dev.txt

# frontend
(cd frontend && npm install && npm run build)

# run (SQLite, auto-migrates and seeds the 200-slot vocabulary)
export PYTHONPATH=backend:ml
export BOOTSTRAP_ADMIN_EMAIL=you@example.org BOOTSTRAP_ADMIN_PASSWORD='a-long-password'
uvicorn app.main:app --app-dir backend --port 8000
```

Open <http://localhost:8000> and sign in with the bootstrap admin. Interactive API docs are at `/api/docs`. Run `cd frontend && npm run dev` to rebuild the client on change.

<details><summary><b>Environment variables</b></summary>

Copy [`.env.example`](.env.example). Placeholders only; never commit `.env`.

| Variable | Purpose | Default |
|---|---|---|
| `ISL_NOVA_ENV` | `production` enforces a strong secret, no synthetic models, no wildcard CORS | `development` |
| `DATABASE_URL` | `sqlite:///…` or `postgresql://user:pass@host/db` | SQLite in `storage/` |
| `JWT_SECRET` | ≥ 32 random characters (required in production) | ephemeral in dev |
| `CORS_ORIGINS` | comma-separated origins | `http://localhost:5173,http://localhost:8000` |
| `STORAGE_DIR` / `MODEL_REGISTRY_DIR` | object storage and model registry paths | `storage/objects`, `artifacts/models` |
| `BOOTSTRAP_ADMIN_EMAIL` / `_PASSWORD` | ensure an admin exists at startup | - |
| `MAX_UPLOAD_MB`, `ANALYSIS_RETENTION_HOURS` | upload limit, analysis retention | 50, 24 |
| `RATE_LIMIT_PER_MINUTE`, `AUTH_RATE_LIMIT_PER_MINUTE` | per-IP limits | 120, 10 |
| `ISL_NOVA_HAND_MODEL`, `ISL_NOVA_POSE_MODEL` | MediaPipe `.task` files for server-side extraction | - |

</details>

<details><summary><b>Docker (PostgreSQL 16 + app)</b></summary>

```bash
cp .env.example .env    # set JWT_SECRET, POSTGRES_PASSWORD, BOOTSTRAP_ADMIN_*
docker compose up --build
```

Migrations run automatically on start (`python -m app.migrate`). To run them manually: `PYTHONPATH=backend:ml python -m app.migrate --status`. To print the PostgreSQL DDL: `python -m app.migrate --render postgresql`.

</details>

## 🗂 The 200-class dataset

Vocabulary slots `ISL001`–`ISL200` are derived from the class list of **INCLUDE** (AI4Bharat / IIT Madras, ACM MM 2020, CC BY 4.0). The 63 remaining INCLUDE glosses are held in reserve, each with a documented reason.

| Metric | Count |
|---|---:|
| Class slots created | **200** |
| Linguistically verified entries | **0** |
| Entries with a licensed reference source | 200 |
| INCLUDE videos listed for these classes (official split) | 3,392 |
| INCLUDE videos downloaded and processed (GitHub Actions, checksum-verified) | 4,284 in 44 parts (56.75 GB) |
| Usable landmark sequences for the 200 classes | **3,370** (train 2,461 · val 274 · test 635), 0 failed, 15 flagged insufficient |
| Classes with authentic local (app-recorded) recordings | 0 |
| Classes trained / evaluated on INCLUDE | **200 / 200** (189 have samples in all three splits) |
| Classes approved for training through the in-app review workflow | 0 (needs linguistic verification) |

<details><summary>Slots by planning category (target vs actual)</summary>

| Category | Target | Slots |
|---|---:|---:|
| Greetings / social | 20 | 19 |
| People / family | 20 | 20 |
| Everyday actions | 25 | **2** |
| Objects / places | 20 | 27 |
| Food / daily needs | 20 | 16 |
| Numbers / time / calendar | 20 | 25 |
| Emotions / feelings / states | 20 | 14 |
| Questions / communication / pronouns | 20 | 14 |
| Education / work | 20 | 15 |
| Travel / directions / emergencies | 15 | 14 |
| Descriptions / colours *(added)* | - | 27 |
| Animals / nature *(added)* | - | 7 |

INCLUDE has few everyday verbs and no food or question words. Closing these gaps needs new consented recordings.
</details>

**Statuses.** Verification moves `proposed → reference_found → review_pending → verified | rejected`, and only the `linguist` role can verify. Data readiness moves `no_data → collecting → ready_for_review → insufficient_data → approved_for_training` (or `excluded`). It is computed by the server: **a verified sign, ≥ 10 approved recordings and ≥ 3 signers**.

**Recording protocol.** Register a pseudonymous signer, record informed consent (with scopes and optional retention), open a session (lighting, background, distance), then record a 2.5 s clip with landmarks. Automatic checks run on upload. One person annotates, a different reviewer approves, and the result is frozen into an immutable dataset version with a signer-independent split. Details: [docs/DATASET_PROTOCOL.md](docs/DATASET_PROTOCOL.md) · [dataset/README.md](dataset/README.md).

**Sources reviewed:** INCLUDE (adopted) · iSign (CC BY-NC-SA, gated, sentence-level: not adopted) · ISLRTC dictionary (no reuse licence established: not used) · GloSL (not identified; link needed). Nothing was scraped.

## 🧠 Train a model

**Reproduce the published model on GitHub Actions (no local download).** Two manual workflows separate data from training, so the videos are downloaded once:

1. **`INCLUDE data pipeline`** (`.github/workflows/include-data.yml`) runs a preflight (runner resources, Zenodo record and licence, vocabulary mapping). It then downloads each Zenodo part with MD5 verification, extracts MediaPipe hand and pose landmarks, deletes the raw video, and merges everything into the `include-landmarks-v1` artifact (176 MB).
2. **`INCLUDE training`** (`.github/workflows/include-train.yml`) trains LSTM, GRU, logistic regression and DTW in parallel on that artifact. It selects by **validation** macro-F1, re-runs the test split through the production `Predictor`, and publishes the selected model as a pre-release.

Start them with *Actions → Run workflow* once the files are on the default branch. Before that, push the run branch: `git push origin HEAD:run/include-data` (settings in `ml/runs/include-data.json`), then `HEAD:run/include-train` (`ml/runs/include-train.json`).

**Install the published model into any deployment:**

```bash
PYTHONPATH=backend:ml python scripts/fetch_model.py --tag model-lstm-20261104T041414Z-s13 \
  --registry artifacts/models --promote        # checksum-verified; restart the server to load it
# Docker: docker compose exec app python /app/scripts/fetch_model.py --tag <tag> --registry /data/models --promote
```

**Or locally**, with the videos on your own disk:

```bash
# 1. get data: INCLUDE videos (56.8 GB) from https://zenodo.org/records/4010759
#    and MediaPipe hand_landmarker.task + pose_landmarker_lite.task
PYTHONPATH=ml python -m isl_nova_ml.include_import --include-root /data/INCLUDE \
  --out data/processed/include --hand-model models/hand_landmarker.task \
  --pose-model models/pose_landmarker_lite.task            # review, then re-run with --approve

# 2. train the LSTM baseline (also: gru.json, pooled-logreg.json, dtw-1nn.json)
PYTHONPATH=ml python -m isl_nova_ml.train --config ml/configs/lstm_baseline.json \
  --manifest data/processed/include/manifest.json --data-root data/processed/include \
  --registry artifacts/models --dataset-version include-official-v1

# 3. review artifacts/models/<id>/metrics.json, then promote in AI Laboratory → Registry
```

Recordings collected in the app train through *AI Laboratory → Experiments* (background job on a frozen dataset version). The pipeline enforces approval, licence and consent; aborts on split leakage; selects on validation only; fits temperature scaling and the rejection threshold on validation; and evaluates the test split once. It writes top-1/top-5, macro/weighted F1, per-class report, confusion matrix, ECE, open-set AUROC, per-signer accuracy, latency and model size.

> [!NOTE]
> `python -m isl_nova_ml.smoke` trains on **procedurally generated, non-ISL** trajectories to check that the code works. Those models are flagged `synthetic`, use class IDs `SYN…`, and cannot be promoted in production.

## 📊 Results

**Genuine results** from GitHub Actions run [41771084083](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41771084083) on data run [41764539272](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41764539272). Dataset `include-official-v1`, 200 classes, INCLUDE official train/val/test split, feature contract `isl-nova-fc-1.0.0`, seed 13. The test split was evaluated once, after model selection on validation.

| Model | Val macro-F1 | Test top-1 | Test top-5 | Precision (macro) | Recall (macro) | Macro-F1 | Weighted-F1 | ECE | Latency / sample | Size |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **LSTM** (selected) | 91.1 % | **91.7 %** | 98.3 % | 93.0 % | 92.4 % | **91.7 %** | 91.5 % | 0.027 | 0.73 ms | 1.78 MB |
| Logistic regression (pooled stats) | 88.1 % | 89.1 % | 98.3 % | 90.4 % | 89.9 % | 88.8 % | 88.9 % | 0.024 | 0.02 ms | 0.99 MB |
| GRU | 86.7 % | 86.5 % | 97.6 % | 88.0 % | 87.4 % | 86.1 % | 85.8 % | 0.017 | 0.17 ms | 1.44 MB |
| DTW 1-NN | 80.7 % | 84.4 % | 94.6 % | 85.7 % | 84.8 % | 83.5 % | 83.8 % | 0.040 | 130 ms | 64 MB |

Sample counts used: 2,448 train / 272 val / 635 test. The 15 insufficient-input sequences were excluded by the feature contract. Latency is batched model time per sample on a 4-vCPU runner.

**End-to-end check.** The published LSTM was loaded through `isl_nova_ml.inference.Predictor` (the code the API uses) and run on all 635 test sequences. It reproduced **91.65 % top-1 / 98.27 % top-5**. States: 556 *recognized*, 57 *uncertain*, 22 *unknown*. Median latency per call was 24 ms, including feature extraction. In this sandbox the release was installed with `scripts/fetch_model.py`, and 24 held-out test sequences sent to `POST /api/v1/predict/sequence` came back 24/24 correct and *recognized*.

<p align="center"><img src="docs/screenshots/ai-laboratory-model.png" alt="AI Laboratory showing the trained LSTM's held-out metrics" width="49%" /> <img src="docs/screenshots/evaluation.png" alt="Per-class F1 and 200-class confusion matrix" width="49%" /></p>

### Unknown signs (open set)

The same model, unchanged, was scored on 887 recordings of **62 INCLUDE glosses outside the vocabulary**. These glosses were never used for training, calibration or choosing the threshold (run [41815223675](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41815223675)).

| AUROC (known vs unknown) | Unknown signs wrongly *recognized* | Unknown answered *uncertain* / *unknown* | Known signs recognized **and** correct |
|:---:|:---:|:---:|:---:|
| **0.900** | **29.3 %** | 36.0 % / 34.3 % | 84.4 % |

Roughly 3 in 10 signs outside the vocabulary get mapped confidently to a known sign. The UI therefore always shows the top-5 alternatives and the decision state, and never speaks a result on its own. Raising the threshold to 0.80 would let through 17 % of unknown signs instead, at the cost of rejecting 18 % of known signs. Full sweep: [research/OPEN_SET_EVALUATION.md](research/OPEN_SET_EVALUATION.md).

### From raw video

LIVEEVAL_BLOCK

> [!WARNING]
> **What these numbers do not show.** INCLUDE has no signer IDs, so this is **not** signer-independent evaluation and says nothing about unseen signers. All signers come from one school in Chennai. Many classes have only 1–4 test videos, so per-class scores are noisy. **Live webcam accuracy with a real person has not been measured.** The new-signer workflow exists, but no new-signer recordings exist yet.

Artifacts: model release [`model-lstm-20261104T041414Z-s13`](https://github.com/nvaltryek-001/ISL-NOVA/releases/tag/model-lstm-20261104T041414Z-s13) (weights, SHA-256, comparison, verification, test-landmark sample). The workflow artifacts `include-landmarks-v1` and `include-models` are kept for 90 days. Full model card: [docs/MODEL_CARD.md](docs/MODEL_CARD.md) · [research/RESULTS.md](research/RESULTS.md).

Measured engineering latency (2 vCPU sandbox, synthetic input, untrained 200-class models; [details](docs/PERFORMANCE_BENCHMARK.md)):

| Operation | Median |
|---|---:|
| Feature extraction, 45 frames → 32×204 | 18.8 ms |
| LSTM inference (h = 128, 222k params) | 2.7 ms |
| GRU inference (h = 128, 179k params) | 1.8 ms |
| `GET /api/v1/signs?q=…` | 3.5 ms |

## 🧪 Implemented vs tested

| Capability | Implemented | How it was tested | Evidence |
|---|:---:|---|---|
| 200-class recognition (INCLUDE official split) | ✅ | Genuine held-out test split, evaluated once | 91.7 % top-1 · [run 41771084083](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41771084083) |
| Production inference path (`Predictor`, API) | ✅ | All 635 test sequences re-run; 24 samples through `POST /predict/sequence` in CI and on the live demo | 91.65 % · 24/24 |
| Unknown-sign rejection | ✅ | 887 held-out out-of-vocabulary recordings (62 glosses) | AUROC 0.900, **29.3 % false recognition** |
| Raw video → MediaPipe → model | ✅ | 73 held-out test videos, server-side extraction | 67/73 (91.8 %) |
| In-browser MediaPipe (GPU/CPU) | ✅ | CI Chromium: bundle, WASM, hand model on GPU and CPU, UI fps badge | [run 41815175935](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41815175935) |
| Browser capture flow on held-out video (virtual camera) | ✅ | INCLUDE test clips played as Chromium's webcam through the Live page | LIVEEVAL_CELL |
| Live webcam with a real person | ✅ | ⛔ **Not tested.** There is no camera or person in the build environment | — |
| Accuracy on new signers | ✅ workflow | ⛔ **No data.** Code path tested with synthetic recordings only | `test_new_signer_evaluation_run` |
| Linguistic verification of 200 signs | ✅ workflow | Workflow tested (API + E2E); **0 signs verified**, no approvals made | [protocol](docs/VERIFICATION_PROTOCOL.md) |
| RBAC, consent, four-eyes review, erasure | ✅ | pytest on SQLite + PostgreSQL 16, E2E | CI |
| Responsive + accessibility basics | ✅ | E2E: 11 routes × 360/768/1280 px + wide font; labels, alt, names, landmarks | CI |
| Free-tier deployment with model | ✅ | Public `/health`, `/model/info`; start-up log shows the SHA-256-verified install | [isl-nova.onrender.com](https://isl-nova.onrender.com) |

## 🌐 Live demo

**[https://isl-nova.onrender.com](https://isl-nova.onrender.com)**: Render free plan, Docker image from this branch, with the released LSTM installed at start-up and verified by SHA-256.

* The first request after ~15 minutes idle takes about a minute while the free instance wakes.
* The demo database is **temporary**: it is reset on every restart or redeploy. Register as a learner to try Live Recognition, Sign Explorer, Communication and the Academy. There is no admin account on the demo.
* Recognition runs MediaPipe **in your browser**; only landmarks are sent to the server. Please **do not upload recordings of real signers** to the demo.

## 🔌 API

84 operations under `/api/v1`, documented in [docs/API_CONTRACT.md](docs/API_CONTRACT.md) (generated from the code) and served live at `/api/v1/openapi.json` and `/api/docs`.

<details><summary>Highlights</summary>

```text
GET    /health                         POST /auth/register · /auth/login · GET/PATCH /me
GET    /signs?q=&category=&status=     GET /signs/{id}   POST /signs   PATCH /signs/{id}
DELETE /signs/{id} (retire)            POST /signs/{id}/review   PUT /signs/{id}/translations/{lang}
POST   /predict/sequence               GET /model/info · /model/metrics
GET    /dataset/stats · /dataset/signs POST /dataset/recordings (multipart) · /dataset/validate
POST   /dataset/signers · /dataset/signers/{id}/consents · /dataset/consents/{id}/revoke
GET    /annotations  POST /annotations  PATCH /annotations/{id}
GET/POST /dataset/versions             GET /dataset/versions/{id}/manifest
GET/POST /experiments  POST /experiments/{id}/run   GET /models  POST /models/{id}/promote · /models/rollback
GET    /evaluation/metrics · /evaluation/confusion-matrix   POST/GET /evaluation/runs (new signers)
GET    /signs/review-sheet.csv (linguists)
GET    /history  POST /feedback  GET /learning/progress  POST /learning/attempts  GET /learning/quiz
```
</details>

## ✅ Testing

| Suite | Command | Last result |
|---|---|---|
| Lint | `ruff check backend ml dataset/scripts scripts` | ✅ pass |
| Backend + ML | `pytest -q` | ✅ **60 passed**, 1 skipped (needs a MediaPipe model file) |
| Backend on PostgreSQL 16 | `TEST_DATABASE_URL=postgresql://… pytest backend/tests` | ✅ pass (CI) |
| Frontend types | `cd frontend && npm run typecheck` | ✅ pass |
| Frontend unit + Python↔TS feature parity | `npm test` | ✅ **16 passed** |
| End-to-end (Chromium) | `npm run build && npm run e2e` | ✅ **19 passed** in CI: 16 app + 3 with the real model (24/24 held-out samples) |
| Docker image + container health | GitHub Actions `docker` job | ✅ pass |
| Deployed instance (read-only) | `.github/workflows/deploy-smoke.yml` | SMOKE_RESULT |

Latest CI on this branch: [run 41815644645](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41815644645): all jobs green.

The E2E suite covers:
* startup, registration and RBAC;
* search and sign CRUD, plus the linguist flow (document the sign, then complete the checklist, then verify);
* the full consent → record → four-eyes review flow;
* model-unavailable and camera-denied states, and kiosk mode;
* every route for one `h1` and no unnamed buttons;
* the light/dark theme toggle;
* layout and accessibility at 360, 768 and 1280 px.

Bugs the tests caught and how they were fixed: [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md).

**Staged evaluation workflows.** These are manual, triggered by pushing a `run/*` branch, with settings in `ml/runs/*.json`:

| Workflow | What it does |
|---|---|
| `include-data.yml` | Preflight, Zenodo download (MD5), MediaPipe extraction in parallel, merge. Raw video never leaves the runner. |
| `include-train.yml` | Trains LSTM, GRU, LogReg and DTW; compares on validation; verifies; publishes a pre-release |
| `include-open-set.yml` | Known test split vs out-of-vocabulary glosses |
| `include-live-eval.yml` | Held-out clips as Chromium's virtual webcam, through the Live page |
| `mediapipe-check.yml` | Diagnoses in-browser MediaPipe loading |
| `deploy-smoke.yml` | Read-only checks of a running deployment |

## ☁️ Deployment

**Live:** [isl-nova.onrender.com](https://isl-nova.onrender.com) (Render free plan, no paid resources). See [Live demo](#-live-demo).

The multi-stage [`Dockerfile`](Dockerfile) builds the SPA and the Python API into one image. [`scripts/docker-entrypoint.sh`](scripts/docker-entrypoint.sh) then:
1. applies migrations;
2. installs the released model when `ISL_NOVA_MODEL_TAG` is set (verified by SHA-256; a failure is logged and the API reports `model_unavailable` instead of crashing);
3. serves on `$PORT`.

[`docker-compose.yml`](docker-compose.yml) adds PostgreSQL 16 for a persistent setup. Environment variables, the free-plan trade-offs, a persistent setup, HTTPS/CORS, a post-deploy checklist and rollback are covered in [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md).

```bash
docker build -t isl-nova .
docker run -p 8000:8000 -e ISL_NOVA_ENV=production -e JWT_SECRET=$(openssl rand -hex 32) \
  -e CORS_ORIGINS=http://localhost:8000 -e ISL_NOVA_MODEL_TAG=model-lstm-20261104T041414Z-s13 isl-nova
```

## 🔬 Research

Research questions (signer-independent recognition, feature ablations, open-set rejection, recording conditions, official vs signer-independent split), protocols and a paper outline: [research/](research/). Highlights: [signer-independent protocol](research/SIGNER_INDEPENDENT_PROTOCOL.md) · [open-set evaluation](research/OPEN_SET_EVALUATION.md) · [ablations](research/ABLATION_STUDY.md) · [literature](research/LITERATURE_REVIEW.md).

## 🔐 Privacy and data governance

Pseudonymous signers, explicit consent scopes, withdrawal as erasure, four-eyes review, audited media access, and landmarks rather than video for live use. Synthetic data is never mixed with real data. See [DATA_GOVERNANCE](docs/DATA_GOVERNANCE.md), [SECURITY_ARCHITECTURE](docs/SECURITY_ARCHITECTURE.md) and the [privacy notice template](docs/PRIVACY_POLICY.md).

## ⚠️ Limitations

Results are on INCLUDE's official split, not signer-independent · unknown-sign rejection is weak (29 % of unseen signs recognized) · no live-person webcam test · vocabulary unverified · category gaps · INCLUDE has no signer IDs, so its split cannot be proven signer-independent · isolated signs only, no grammatical translation · no non-manual features · CPU NumPy models · not yet tested with Deaf users. Full list: [research/LIMITATIONS.md](research/LIMITATIONS.md).

## 📁 Repository structure

```text
backend/app/            API: framework, routers, db, migrations, security, services
backend/tests/          API, RBAC, dataset, consent, inference-state tests
ml/isl_nova_ml/         feature contract, models, training, registry, inference, INCLUDE importer
ml/configs/             experiment configs (LSTM baseline, GRU, LogReg, DTW)
ml/tests/               contract, gradients, splits/leakage, registry, parity fixture
frontend/src/           React app: pages/, components/, lib/ (api, query, router, store, features, landmarks)
frontend/tests/         unit tests, parity test, Playwright E2E
dataset/                vocabulary CSVs, manifests, INCLUDE label map + splits, generator
docs/                   architecture, API, schema, protocols, model card, deployment, status
research/               questions, protocols, results template, references
scripts/                API-doc generator, benchmark
```

## 🤝 Contributing

Read [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md). In short: no invented data or metrics, linguist role only for qualified ISL reviewers, never commit media or weights, and all checks must pass.

## 📜 Licence and attribution

**No licence has been chosen for this repository yet.** Until the owner adds a `LICENSE` file, default copyright applies.

* Vocabulary glosses and split lists derive from **INCLUDE** by A. Sridhar, R. G. Ganesan, P. Kumar and M. Khapra (AI4Bharat, IIT Madras). Dataset: CC BY 4.0. Code and label maps: MIT ([`dataset/sources/include/`](dataset/sources/include/)).
* MediaPipe (Google) is loaded at runtime under its own licence.

## 🗺 Roadmap

Import INCLUDE and train the baseline → recruit ISL reviewers → collect signer-labelled recordings for a true signer-independent test set → TCN/Transformer candidates and ablations → S3 storage, scheduled retention purge, shared rate limiting → Hindi/Kannada UI. Details: [docs/DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md).

## 📚 References

* Sridhar, A., Ganesan, R. G., Kumar, P., Khapra, M. (2020). *INCLUDE: A Large Scale Dataset for Indian Sign Language Recognition.* ACM Multimedia. [doi:10.1145/3394171.3413528](https://doi.org/10.1145/3394171.3413528)
* Joshi, A. et al. (2024). *iSign: A Benchmark for Indian Sign Language Processing.* Findings of ACL. [doi:10.18653/v1/2024.findings-acl.643](https://doi.org/10.18653/v1/2024.findings-acl.643)
* Hochreiter, S., Schmidhuber, J. (1997). *Long Short-Term Memory.* Neural Computation 9(8). [doi:10.1162/neco.1997.9.8.1735](https://doi.org/10.1162/neco.1997.9.8.1735)
* Guo, C. et al. (2017). *On Calibration of Modern Neural Networks.* ICML. [arXiv:1706.04599](https://arxiv.org/abs/1706.04599)
* Hendrycks, D., Gimpel, K. (2017). *A Baseline for Detecting Misclassified and Out-of-Distribution Examples.* ICLR. [arXiv:1610.02136](https://arxiv.org/abs/1610.02136)

Full BibTeX: [research/REFERENCES.bib](research/REFERENCES.bib).
