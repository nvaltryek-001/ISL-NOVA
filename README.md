<div align="center">

<img src="frontend/public/favicon.svg" alt="ISL NOVA logo" width="88" />

# ISL NOVA

### Beyond Gestures. Towards Understanding.

An open, consent-first platform for **Indian Sign Language** recognition, learning and dataset building, honest about what it can and cannot do yet.

[![CI](https://github.com/nvaltryek-001/ISL-NOVA/actions/workflows/ci.yml/badge.svg?branch=feat%2Fisl-nova-platform)](https://github.com/nvaltryek-001/ISL-NOVA/actions/workflows/ci.yml)
![version](https://img.shields.io/badge/version-0.1.0-8b5cf6)
![python](https://img.shields.io/badge/python-3.13-3776ab)
![react](https://img.shields.io/badge/react-19.2-22d3ee)
![model](https://img.shields.io/badge/trained%20model-none%20yet-f43f5e)

</div>

> [!IMPORTANT]
> **Project status, stated plainly.** The full software platform is built and tested: 200 vocabulary slots, the consent-first data pipeline, the training and evaluation pipeline, webcam recognition, and every application module.
> **No recognition model has been trained on real ISL data yet**, and **none of the 200 signs has been linguistically verified**. The app says so wherever it matters (`model unavailable`). The steps to train the first real model are in [Train a model](#-train-a-model).

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
| **Live Recognition Studio** | Webcam with camera selection, in-browser MediaPipe hand + pose landmarks and overlay, *capture one sign* or continuous sliding window, top-5 with smoothing, states `recognized · uncertain · unknown · insufficient_input · model_unavailable · camera_unavailable`, meanings in en/hi/kn, speech, copy, save, correction reports. **Video never leaves the device.** |
| **Video Analysis** | Validated upload (magic bytes, decode, size), background job, hand-tracking timeline, windowed inference when a model exists, JSON export, 24-hour auto-deletion |
| **Sign Explorer** | Multilingual search, category/status filters, sign detail with licensed references, review log, related signs, bookmarks, correction reports; reviewers get **full CRUD** (create, edit, retire/restore, references, translations) |
| **Communication Workspace** | Word-by-word composer from sign meanings, editable text, speech, copy/share, saved phrases. It is clearly labelled as *not* an ISL translator. |
| **Learning Academy** | Lessons by category, quizzes built **only from verified signs and verified meanings**, progress and "review these signs" |
| **Dataset Intelligence Lab** | Readiness funnel and per-class table, pseudonymous signers, consent scopes and withdrawal, sessions, **Recording Studio** (countdown, MediaRecorder + landmarks, quality badges), four-eyes review queue, validation, immutable versioned manifests |
| **AI Laboratory** | Active model, held-out metrics, per-class report and confusion matrix, model registry with promote/rollback, experiments run as background jobs, feature-contract viewer |
| **Research Centre** | Research questions, evidence status, protocol documents, verified references, intentionally empty results table |
| **3D Visualisation** *(experimental)* | Record or load real landmark sequences; orbit, frame stepping, speed, wrist trajectories |
| **Admin & Kiosk** | User roles, feedback inbox, audit log; full-screen high-contrast kiosk with large targets, verified quick phrases and one-tap session reset |

**Design:** a clean **light theme by default** (white cards on a soft violet-tinted canvas, deep-violet accents, AA-contrast status colours) with a one-click **dark theme** toggle in the header, or *match my device* in Settings. Both themes share one token system (`frontend/src/styles.css`).

Accessibility throughout: keyboard navigation and visible focus, skip link, labelled controls, high-contrast, reduced-motion and large-text modes, and a responsive layout tested at 390 px.

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

All screenshots were captured by the Playwright suite from the running application, on freshly seeded data. They show the real state: 200 unverified slots and no model.

| | |
|---|---|
| ![Live recognition: camera on, model unavailable notice](docs/screenshots/live-recognition.png) **Live Recognition.** Fake test camera; in the offline sandbox MediaPipe could not load, and the UI says so. | ![Sign detail with licensed reference and review workflow](docs/screenshots/sign-detail.png) **Sign detail.** Licensed source, pending meanings, review workflow. |
| ![Dataset Lab readiness funnel](docs/screenshots/dataset-lab.png) **Dataset Lab.** Readiness funnel and per-class table. | ![Sign explorer grid](docs/screenshots/sign-explorer.png) **Sign Explorer.** 200 slots, searchable. |
| ![Communication composer](docs/screenshots/communication.png) **Communication.** Composer with unverified-meaning warnings. | ![Kiosk mode](docs/screenshots/kiosk.png) **Kiosk.** High-contrast, large targets. |

<details><summary>More: dark theme · AI Laboratory · mobile</summary>

<img src="docs/screenshots/dashboard-dark.png" alt="Dashboard in dark theme" width="100%" />


<img src="docs/screenshots/ai-laboratory.png" alt="AI Laboratory feature contract" width="72%" /> <img src="docs/screenshots/mobile-dashboard.png" alt="Mobile dashboard" width="24%" />

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
| External reference videos listed (INCLUDE official split) | 3,392, **not downloaded** |
| Classes with authentic local recordings | 0 |
| Classes approved for training | 0 |
| Classes used for training / evaluated | 0 / 0 |

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

**No recognition results exist yet.** No model has been trained on authentic ISL data, so there is no accuracy to report. [docs/MODEL_CARD.md](docs/MODEL_CARD.md) and [research/RESULTS_TEMPLATE.md](research/RESULTS_TEMPLATE.md) will be filled from `metrics.json` when one is.

Measured engineering latency (2 vCPU sandbox, synthetic input, untrained 200-class models; [details](docs/PERFORMANCE_BENCHMARK.md)):

| Operation | Median |
|---|---:|
| Feature extraction, 45 frames → 32×204 | 18.8 ms |
| LSTM inference (h = 128, 222k params) | 2.7 ms |
| GRU inference (h = 128, 179k params) | 1.8 ms |
| `GET /api/v1/signs?q=…` | 3.5 ms |

## 🔌 API

80 operations under `/api/v1`, documented in [docs/API_CONTRACT.md](docs/API_CONTRACT.md) (generated from the code) and served live at `/api/v1/openapi.json` and `/api/docs`.

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
GET    /evaluation/metrics · /evaluation/confusion-matrix
GET    /history  POST /feedback  GET /learning/progress  POST /learning/attempts  GET /learning/quiz
```
</details>

## ✅ Testing

| Suite | Command | Last result |
|---|---|---|
| Lint | `ruff check backend ml dataset/scripts scripts` | ✅ pass |
| Backend + ML | `pytest -q` | ✅ 56 passed, 1 skipped (needs a MediaPipe model file) |
| Backend on PostgreSQL | `TEST_DATABASE_URL=postgresql://… pytest backend/tests` | ✅ pass (CI) |
| Docker image + health check | GitHub Actions `docker` job | ✅ pass (CI) |
| Frontend types | `cd frontend && npm run typecheck` | ✅ pass |
| Frontend unit + feature parity | `npm test` | ✅ 16 passed |
| End-to-end (Chromium, fake camera) | `npm run build && npm run e2e` | ✅ 15 passed |

The E2E suite covers startup, registration and RBAC, search, sign CRUD, linguist verification, the full consent → record → four-eyes review flow, model-unavailable and camera-denied states, kiosk, every route for a single `h1` and unnamed buttons, the light/dark theme toggle, and the 390 px layout. Evidence and the bugs the tests caught: [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md).

## ☁️ Deployment

**Not deployed; there is no live URL.** The repository ships a multi-stage [`Dockerfile`](Dockerfile), [`docker-compose.yml`](docker-compose.yml) with PostgreSQL 16 and health checks; CI builds the image and checks its health endpoint. Platform steps (Render / Fly.io / Railway), HTTPS/CORS, storage, a post-deploy checklist and rollback are in [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md). Deploying needs a platform account and approval for any paid resources.

## 🔬 Research

Research questions (signer-independent recognition, feature ablations, open-set rejection, recording conditions, official vs signer-independent split), protocols and a paper outline: [research/](research/). Highlights: [signer-independent protocol](research/SIGNER_INDEPENDENT_PROTOCOL.md) · [open-set evaluation](research/OPEN_SET_EVALUATION.md) · [ablations](research/ABLATION_STUDY.md) · [literature](research/LITERATURE_REVIEW.md).

## 🔐 Privacy and data governance

Pseudonymous signers, explicit consent scopes, withdrawal as erasure, four-eyes review, audited media access, and landmarks rather than video for live use. Synthetic data is never mixed with real data. See [DATA_GOVERNANCE](docs/DATA_GOVERNANCE.md), [SECURITY_ARCHITECTURE](docs/SECURITY_ARCHITECTURE.md) and the [privacy notice template](docs/PRIVACY_POLICY.md).

## ⚠️ Limitations

No trained model yet · vocabulary unverified · category gaps · INCLUDE has no signer IDs, so its split cannot be proven signer-independent · isolated signs only, no grammatical translation · no non-manual features · CPU NumPy models · not yet tested with Deaf users. Full list: [research/LIMITATIONS.md](research/LIMITATIONS.md).

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
