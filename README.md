<div align="center">

<img src="frontend/public/favicon.svg" alt="ISL NOVA logo" width="96" />

# ISL NOVA

### Beyond Gestures. Towards Understanding.

**An open, consent-first platform for Indian Sign Language recognition, learning and dataset building,<br/>honest about what it can and cannot do yet.**

[![CI](https://github.com/nvaltryek-001/ISL-NOVA/actions/workflows/ci.yml/badge.svg?branch=feat%2Fisl-nova-v2)](https://github.com/nvaltryek-001/ISL-NOVA/actions/workflows/ci.yml)
[![Windows setup](https://github.com/nvaltryek-001/ISL-NOVA/actions/workflows/windows-local.yml/badge.svg?branch=run%2Fwindows-check)](https://github.com/nvaltryek-001/ISL-NOVA/actions/workflows/windows-local.yml)
![version](https://img.shields.io/badge/version-2.0.0-8b5cf6)
![python](https://img.shields.io/badge/python-3.11%E2%80%933.13-3776ab)
![node](https://img.shields.io/badge/node-22-5fa04e)
![react](https://img.shields.io/badge/react-19.2-22d3ee)
<br/>
![model](https://img.shields.io/badge/BiLSTM--attention%20v3%20·%20200%20signs-95.1%25%20top--1%20(INCLUDE%20test)-10b981)
![browser](https://img.shields.io/badge/browser%20pipeline-84.9%25%20top--1-10b981)
![languages](https://img.shields.io/badge/languages-English%20·%20हिन्दी%20·%20ಕನ್ನಡ-22d3ee)
![open-set](https://img.shields.io/badge/unknown%20signs%20accepted-8.8%25%20(target%20%3C10%25)-10b981)
![verified](https://img.shields.io/badge/linguistically%20verified-0%20%2F%20200-ef4444)
[![demo](https://img.shields.io/badge/live%20demo-isl--nova.onrender.com-8b5cf6)](https://isl-nova.onrender.com)

<p>
  <a href="https://isl-nova.onrender.com"><b>🌐 Live demo</b></a> ·
  <a href="#-results"><b>📊 Results</b></a> ·
  <a href="#-implemented-vs-tested"><b>🧪 What is tested</b></a> ·
  <a href="#-windows-setup"><b>🪟 Windows setup</b></a> ·
  <a href="docs/MODEL_CARD.md"><b>📄 Model card</b></a> ·
  <a href="docs/report/ISL_NOVA_Project_Report.pdf"><b>📘 Project report (PDF)</b></a> ·
  <a href="docs/PROJECT_STATUS.md"><b>📋 Status and remaining work</b></a>
</p>

<img src="docs/screenshots/dashboard-model.png" alt="ISL NOVA dashboard with the trained 200-class model live" width="100%" />

</div>

> [!IMPORTANT]
> **Project status, stated plainly**
>
> | | |
> |---|---|
> | ✅ **Platform** | 17 modules incl. **Practice Coach**, **Text-to-Sign**, **Conversation** (signs split at pauses), **teacher classes**, **analytics**, installable **offline app** with **on-device recognition**; every screen and all 200 sign meanings in **English, हिन्दी and ಕನ್ನಡ**; refresh tokens, sign-out-everywhere, reset codes, **two-factor sign-in**, retention job; optional Redis, S3 storage, Prometheus + Grafana. CI green: **104** Python tests (incl. real Redis, S3 and PostgreSQL), **27** unit tests, **25** end-to-end tests incl. an **axe-core WCAG 2.1 AA scan**. |
> | ✅ **Real model (v3)** | BiLSTM with attention, trained on genuine INCLUDE recordings, **200 signs**: **95.1 % top-1 · 99.4 % top-5** on the 635-video official test split (v1 91.7 %, v2 92.0 %), selected by validation among 21 candidates. Through the full browser pipeline (held-out clips as a virtual webcam): **84.9 % top-1** (v1 74.0 %; target 85 % missed by one clip). |
> | ✅ **Says "I don't know"** | A calibrated detector ships with the model: on 31 out-of-vocabulary glosses never used for any choice, **8.8 %** of unknown signs are accepted and **13.2 %** of known signs held back, meeting both targets (v1 accepted 29 %). |
> | ✅ **Face features (v4)** | Eyebrow, eye and mouth landmarks from all 4,257 videos (face found in 99.94 % of frames), feature contract 2.0.0: +1.3 / +0.7 points for BiLSTM-attention / Transformer, −0.9 for TCN; best single model 97.3 %. Not made the default: it ties the v3 model on validation and misses the unknown-sign target (14.2 %). [Write-up](research/V4_FACE_FEATURES.md) |
> | ⏸️ **Deployed (v1)** | The free demo at **[isl-nova.onrender.com](https://isl-nova.onrender.com)** still runs v1; switching it to `main` waits for the owner's go-ahead. |
> | ⚠️ **Hindi / Kannada** | All 200 meanings exist as **machine drafts**, clearly marked; **0 verified by a linguist**. |
> | ⛔ **Not yet shown** | Accuracy on **new signers** (INCLUDE has no signer IDs, so results are **not signer-independent**) · recognition with **a real person at a webcam** · **linguistic verification** (0 / 200 signs verified) · any user study. |

---

## 📚 Contents

<table>
<tr><td valign="top">

**Overview**
- [Introduction](#-introduction)
- [Problem statement](#-problem-statement)
- [Objectives](#-objectives)
- [Key features](#-key-features)
- [Application modules](#-application-modules)
- [Screenshots](#-screenshots)

</td><td valign="top">

**System**
- [Architecture](#-architecture)
- [System workflow](#-system-workflow)
- [Technology stack](#-technology-stack)
- [Dataset](#-dataset)
- [ML algorithms](#-ml-algorithms)
- [Results](#-results)
- [Implemented vs tested](#-implemented-vs-tested)

</td><td valign="top">

**Run it**
- [Quick start](#-quick-start)
- [One-command install](#-one-command-install-everything)
- [Windows setup](#-windows-setup)
- [Database setup](#-database-setup)
- [Model installation](#-model-installation)
- [Dataset import and training](#-dataset-import-and-training)
- [Testing](#-testing)
- [Docker](#-docker)
- [Deployment and live demo](#-deployment-and-live-demo)

</td><td valign="top">

**Reference**
- [API](#-api)
- [Environment variables](#-environment-variables)
- [Limitations](#-limitations)
- [Research opportunities](#-research-opportunities)
- [Repository structure](#-repository-structure)
- [Licence and attribution](#-licence-and-attribution)
- [Contributors](#-contributors)
- [References](#-references)

</td></tr>
</table>

---

## 💡 Introduction

ISL NOVA recognises **isolated Indian Sign Language (ISL) signs** from a webcam, teaches them, and helps a team build a consented, signer-labelled ISL dataset. Hand and body landmarks are extracted **in the browser** with MediaPipe; only landmark coordinates (never video) reach the server, where a calibrated sequence model answers with one of five honest states: *recognized*, *uncertain*, *unknown*, *insufficient input* or *model unavailable*.

It is one Python service plus a React web app, with a 200-sign vocabulary (`ISL001`–`ISL200`), a real model trained on the INCLUDE dataset, and the review, consent and evaluation machinery needed to make future results trustworthy.

## ❓ Problem statement

India has millions of Deaf people and very few ISL interpreters. Software can help with practice and simple communication, but:

* **Data is scarce and often unconsented.** Few openly licensed ISL datasets exist, and fewer record who signed and what they agreed to.
* **Accuracy claims are inflated.** Many demos test on the same signers they trained on, so the number says little about a new user.
* **Systems guess.** A classifier always returns *some* class, even for a sign it has never seen, a half-visible hand or an empty frame.
* **Vocabulary is unverified.** Glosses copied from a dataset are labels, not reviewed ISL descriptions.

## 🎯 Objectives

1. Recognise a **200-sign ISL vocabulary** in real time in the browser, with calibrated confidence and explicit rejection of unknown or poor input.
2. Make every result **traceable**: licensed source, verification state, data readiness, dataset version, model lineage and checksums.
3. Make data collection **consent-first**: no recording without consent, no training without `model_training` consent, withdrawal erases media.
4. Evaluate **honestly**: held-out tests evaluated once, signer-independent splits when signer IDs exist, open-set and new-signer evaluation workflows, and no number reported that was not measured.
5. Be **usable**: learning, communication, kiosk and accessibility features, in light and dark themes, on phone, tablet and desktop.

## ✨ Key features

| | Feature | |
|:---:|---|---|
| 🎥 | **Real-time recognition** | In-browser MediaPipe hand + pose, GPU→CPU fallback, capture-one-sign or continuous mode, top-5 with smoothing, speech and text output |
| 🧭 | **Honest answers** | Temperature-calibrated probabilities, rejection threshold τ + margin → `recognized · uncertain · unknown · insufficient_input · model_unavailable` |
| 🔒 | **Privacy by design** | Video never leaves the device for live use; pseudonymous signers; consent scopes; withdrawal as erasure; audit log |
| 🗂️ | **200-class vocabulary** | `ISL001`–`ISL200` with licensed references, verification and readiness states; meanings in English, Hindi and Kannada with transliteration (Hindi/Kannada are labelled machine drafts until a linguist verifies them) |
| 🌐 | **Three-language interface** | Every screen in English, हिन्दी or ಕನ್ನಡ (switcher in the header, remembered); speech output in the chosen language; translation coverage, review-sheet export and linguist-only import |
| 🎯 | **Practice Coach** | Pick a sign, watch a reference animation built from real INCLUDE landmarks, try it on camera, get a 0–100 similarity score, per-part feedback (hands, shape, movement) and what the model read |
| 🔁 | **Text-to-Sign & Conversation** | Type English or Hindi → the matching signs as reference animations (unknown words flagged); two-way mode: hearing person speaks (speech-to-text), deaf person signs (continuous recognition), each side sees the other's words. Output is a *recognized word sequence*, **not a translation** |
| 📴 | **Installable & offline** | PWA: install to the home screen; the app shell and MediaPipe assets are cached so it opens offline (recognition still needs the server) |
| 🏅 | **Streaks and badges** | Daily streak, points, weekly goal and seven badges in *My progress*, derived only from your own quiz and Practice Coach attempts |
| 🛡️ | **Account security** | Rotating refresh tokens with reuse detection, sign out everywhere, admin-issued one-time reset codes, optional TOTP two-factor (RFC 6238), audit-logged |
| 📱 | **On-device recognition** | The model also runs in the browser (TypeScript port, identical results): works offline and is the automatic fallback when the server is unreachable |
| 🚫 | **Says "not a sign I know"** | A calibrated unknown-sign detector ships with the model: 8.8 % of unseen out-of-vocabulary signs are accepted, 13.2 % of known signs held back (held-out glosses) |
| 🧑‍🏫 | **Teacher classes** | Teachers create a class and share a code; they see each learner's progress summary and the class's hardest signs. Learners can leave at any time; history and recordings are never shared |
| 📊 | **Analytics** | Activity per day, active and new users, most practised and hardest signs, common corrections; aggregates only |
| 🔁 | **Spaced repetition** | Mistakes come back today, correct answers after 1, 2, 4, 8 and 16 days; daily goal |
| ⚙️ | **Scales out** | Optional Redis (shared rate limit + job queue with worker processes), S3-compatible storage, Prometheus + Grafana dashboard; load-tested |
| ✅ | **Expert verification** | Only the `linguist` role verifies; a documented entry and a three-item checklist are enforced by the API; CSV review sheet for all 200 signs |
| 🧪 | **Full ML lifecycle** | Versioned feature contract, leakage checks, four model families, calibration, registry with promote/rollback, background training jobs |
| 📈 | **Evaluation workflows** | Held-out test, open-set (unknown signs), new-signer evaluation runs with per-signer accuracy, virtual-camera replay |
| ♿ | **Accessible** | Keyboard navigation, skip link, labelled controls, high-contrast, reduced-motion and large-text modes; light/dark themes; checked at 360/768/1280 px |
| 🪟 | **Runs anywhere** | One-command setup on Windows (PowerShell) and Linux/macOS; Docker image; free-tier deployment with the model installed at start-up |

## 🧩 Application modules

| # | Module | What it does |
|:-:|---|---|
| 1 | **Dashboard** | Live counts from the database and registry: slots, verified signs, recordings, training-ready classes, model status, system health |
| 2 | **Live Recognition Studio** | Camera selection, landmark overlay, *capture one sign* (1.5 / 2.5 / 3.5 s, optional countdown) or continuous 2 s sliding window, fps + GPU/CPU badge, top-5, meanings in en/hi/kn, speech, copy, save, correction reports. **Video never leaves the device.** |
| 3 | **Video Analysis** | Validated upload (magic bytes, decode, size), background job, hand-tracking timeline, windowed inference, JSON export, 24-hour auto-deletion |
| 4 | **Sign Explorer** | Multilingual search, filters, detail with licensed references and review log, bookmarks; reviewers get **full CRUD** (create, edit, retire/restore, references, translations); linguists verify with the **checklist** |
| 5 | **Communication Workspace** | Word-by-word composer from sign meanings, editable text, speech, copy/share, saved phrases. Clearly labelled as *not* an ISL translator |
| 6 | **Learning Academy** | Lessons by category; quizzes built **only from verified signs and meanings**; progress and "review these signs" |
| 7 | **Dataset Intelligence Lab** | Readiness funnel, pseudonymous signers, consent and withdrawal, sessions, **Recording Studio**, four-eyes review queue, validation, immutable versioned manifests |
| 8 | **AI Laboratory** | Active model and held-out metrics, per-class report, 200×200 confusion matrix, registry promote/rollback, experiments, **new-signer evaluation**, feature-contract viewer |
| 9 | **Research Centre** | Research questions, evidence status, protocols, verified references |
| 10 | **3D Landmark Viewer** *(experimental)* | Record or load real landmark sequences; orbit, frame stepping, speed, wrist trajectories |
| 11 | **Admin** | User roles, feedback inbox, audit log |
| 12 | **Kiosk Mode** | Full-screen, high-contrast, large targets, verified quick phrases, one-tap session reset |
| 13 | **Practice Coach** | Reference animation from real recordings, scored attempt with per-part tips |
| 14 | **Text to Sign** | English or Hindi words → reference animations of the matching signs |
| 15 | **Conversation** | Speech ↔ signs; signs split at pauses into a *recognized word sequence* (not a translation) |
| 16 | **Classes** | Teacher dashboard and class join codes |
| 17 | **Analytics** | Aggregate usage and learning statistics (admin, researcher) |

Roles (enforced on the server): `admin`, `linguist`, `data_curator`, `researcher`, `learner`.

## 📸 Screenshots

All screenshots were captured by Playwright from the running application.

| | |
|---|---|
| ![AI Laboratory with the trained LSTM's held-out metrics](docs/screenshots/ai-laboratory-model.png) **AI Laboratory.** Held-out metrics read from the model's own `metrics.json`. | ![Per-class F1 and 200-class confusion matrix](docs/screenshots/evaluation.png) **Evaluation.** Per-class F1 and the 200 × 200 confusion matrix. |
| ![Verification dialog with the three-item checklist](docs/screenshots/verification-checklist.png) **Verification.** Document the sign and tick all three checks; Confirm stays disabled until then. | ![New-signer evaluation tab](docs/screenshots/ai-laboratory-new-signers.png) **New signers.** Evaluate the live model on consented recordings from people outside INCLUDE (no such data yet). |
| ![Sign detail with licensed reference and review workflow](docs/screenshots/sign-detail.png) **Sign detail.** Licensed source, pending meanings, review log. | ![Dataset Lab readiness funnel](docs/screenshots/dataset-lab.png) **Dataset Lab.** Readiness funnel and per-class table. |
| ![Communication composer](docs/screenshots/communication.png) **Communication.** Composer with unverified-meaning warnings. | ![Kiosk mode](docs/screenshots/kiosk.png) **Kiosk.** High contrast, large targets. |

<details><summary><b>More: dark theme · Live Recognition · Sign Explorer · mobile</b></summary>

<img src="docs/screenshots/dashboard-dark.png" alt="Dashboard in dark theme" width="100%" />

<img src="docs/screenshots/live-recognition.png" alt="Live recognition page" width="49%" /> <img src="docs/screenshots/sign-explorer.png" alt="Sign explorer grid" width="49%" />

<img src="docs/screenshots/mobile-dashboard.png" alt="Mobile dashboard" width="30%" /> <img src="docs/screenshots/mobile-dataset.png" alt="Mobile Dataset Lab at 360 px" width="30%" />

The Live Recognition capture was taken in the offline build sandbox, before a model was installed and without access to the MediaPipe CDN; the page says so instead of pretending.
</details>

## 🏗 Architecture

```mermaid
flowchart LR
  subgraph Browser["Browser · React 19 + TypeScript + Tailwind v4"]
    CAM[Webcam] --> MP[MediaPipe Tasks<br/>hands + pose]
    MP --> UI[ISL NOVA UI]
  end
  UI -- "landmarks (JSON), never video" --> API
  subgraph Server["Python modular monolith · Starlette + Pydantic"]
    API[/api/v1 · 84 operations/] --> RBAC[Auth · RBAC · rate limits · audit]
    API --> FC[Feature contract<br/>isl-nova-fc-1.0.0 · 32×204]
    FC --> PRED[Calibrated predictor<br/>τ + margin → state]
    API --> JOBS[Background jobs]
    JOBS --> TRAIN[Training pipeline<br/>LSTM · GRU · LogReg · DTW]
    TRAIN --> REG[(Model registry<br/>SHA-256 checked)]
    PRED --> REG
  end
  API --> DB[(PostgreSQL 16 / SQLite)]
  API --> OBJ[(Object storage)]
  INC[(INCLUDE · CC BY 4.0)] -. importer .-> OBJ
```

**Model lifecycle on GitHub Actions** (manual, staged workflows; raw video never leaves the runner):

```mermaid
flowchart LR
  Z[(Zenodo INCLUDE<br/>56.75 GB, MD5)] --> D[include-data<br/>MediaPipe per part]
  D -->|landmarks only| A[(Artifact)]
  A --> T[include-train<br/>4 model families]
  T -->|best on validation| R[(GitHub pre-release<br/>weights + SHA-256)]
  R --> O[include-open-set]
  R --> L[include-live-eval]
  R --> E[docker-entrypoint<br/>ISL_NOVA_MODEL_TAG]
  E --> P[isl-nova.onrender.com]
```

More: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/SECURITY_ARCHITECTURE.md](docs/SECURITY_ARCHITECTURE.md) · [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md).

## 🔄 System workflow

```mermaid
flowchart LR
  A[Webcam frame] --> B[MediaPipe hands + pose<br/>in the browser]
  B --> C[Landmark buffer<br/>timestamps]
  C --> D[Capture window<br/>1.5 / 2.5 / 3.5 s]
  D -->|POST /predict/sequence| E[Feature contract<br/>resample to 32 × 204]
  E --> F[LSTM → softmax<br/>temperature 1.025]
  F --> G{p ≥ τ 0.673<br/>and margin ≥ 0.10?}
  G -- yes --> H[recognized:<br/>sign + meaning + speech]
  G -- "p ≥ 0.6 τ" --> I[uncertain:<br/>top-5 shown]
  G -- no --> J[unknown]
  E -- too few frames / hands --> K[insufficient input]
```

The 204 features per frame are hand landmarks normalised to the wrist and hand scale, body-relative wrist and upper-body pose, two-hand distances, joint angles, presence flags and wrist velocity. The **same contract** is implemented in Python (training and server inference) and TypeScript (browser quality checks), and a parity test keeps them within 2×10⁻⁵. See [docs/FEATURE_CONTRACT.md](docs/FEATURE_CONTRACT.md).

## 🛠 Technology stack

| Layer | Technology |
|---|---|
| Frontend | React 19.2, TypeScript 6 (strict), Tailwind CSS 4.3, esbuild 0.28, in-house router / query cache / store, SVG charts |
| Backend | Python 3.13, Starlette 1.7, Pydantic 2.13, Uvicorn, PyJWT, PBKDF2, versioned SQL migrations, structured JSON logs |
| Data | PostgreSQL 16 (production), SQLite (development and the free demo), path-safe local object storage |
| CV / ML | MediaPipe Tasks (browser 0.10.14, Python 0.10.32), OpenCV 5, NumPy LSTM/GRU with gradient-checked backprop, scikit-learn |
| Quality | pytest, node:test, Playwright (Chromium), Ruff, GitHub Actions (Linux + Windows), Docker |
| Hosting | Docker image on Render free plan; model from a GitHub pre-release |

Why Starlette rather than FastAPI, and esbuild rather than Vite? The build environment had no package-registry access, so the project uses the tested foundations of those tools. Details: [docs/TECH_STACK.md](docs/TECH_STACK.md).

## 🗂 Dataset

Vocabulary slots `ISL001`–`ISL200` come from the class list of **INCLUDE** (AI4Bharat / IIT Madras, ACM MM 2020, **CC BY 4.0**). The other 63 INCLUDE glosses are held in reserve with documented reasons, and 62 of them now serve as the **unknown-sign** test set.

| Metric | Count |
|---|---:|
| Class slots | **200** (`ISL001`–`ISL200`, unique IDs) |
| Entries with a licensed reference source | 200 |
| **Linguistically verified** | **0** |
| INCLUDE videos listed for the 200 classes (official split) | 3,392 |
| INCLUDE videos downloaded and processed (44 Zenodo parts, MD5-verified) | 4,284 (56.75 GB) |
| **Usable landmark sequences, 200 classes** | **3,370**: train 2,461 · val 274 · test 635 |
| Failed videos / insufficient-input sequences | 0 / 15 |
| Classes with samples in all three splits | 189 of 200 |
| **Classes trained / evaluated** | **200 / 200** |
| Out-of-vocabulary sequences (62 reserve glosses, never trained on) | 887 |
| Classes with authentic app-recorded data / approved in-app for training | 0 / 0 |

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

INCLUDE has few everyday verbs and no food or question words; closing these gaps needs new consented recordings.
</details>

**States.** Verification: `proposed → reference_found → review_pending → verified | rejected` (only the `linguist` role verifies; see [docs/VERIFICATION_PROTOCOL.md](docs/VERIFICATION_PROTOCOL.md)). Data readiness: `no_data → collecting → ready_for_review → insufficient_data → approved_for_training` (or `excluded`), computed by the server: a verified sign, ≥ 10 approved recordings and ≥ 3 signers.

**Meanings.** English glosses come from the source. Hindi and Kannada meanings are left *pending* rather than invented.

**Sources reviewed:** INCLUDE (adopted) · iSign (CC BY-NC-SA, gated, sentence-level: not adopted) · ISLRTC dictionary (no reuse licence established: not used). Nothing was scraped. Protocol: [docs/DATASET_PROTOCOL.md](docs/DATASET_PROTOCOL.md) · [dataset/README.md](dataset/README.md).

## 🧠 ML algorithms

| Model | Idea | Implementation |
|---|---|---|
| **BiLSTM-attention** (default since v3) | Bidirectional LSTM (96 per direction), additive attention pooling + mean pooling → softmax | NumPy with hand-written backprop (gradient-checked), Adam, inverse-√frequency class weights, frame-rate augmentation, early stopping on validation |
| **Transformer** | 2-layer pre-LayerNorm encoder, 4 heads, learned positions, mean pooling | NumPy, as above |
| **TCN** | Dilated temporal convolutions (1, 2, 4) with residuals, mean + max pooling | NumPy, as above |
| **Ensembles** | Mean of calibrated member probabilities | members chosen by validation |
| **LSTM** (v1/v2 default) | 1-layer LSTM, hidden 128, last + mean-pooled state → softmax; 222k parameters | NumPy, as above |
| **GRU** | Same shape with gated recurrent units; 179k parameters | NumPy, as above |
| **Logistic regression** | Mean, std, min, max of each feature over time → linear classifier | scikit-learn |
| **DTW 1-NN** | Nearest training sequence under dynamic time warping | Batched NumPy DTW with a Sakoe–Chiba window |

An **unknown-sign detector** (logistic on max-probability, margin, entropy) ships inside the model and decides *recognized / uncertain / unknown*. All models share the feature contract (1.0.0: hands + pose; 2.0.0: + face), select on **validation** only, get **temperature scaling** and a **rejection threshold** fitted on validation, and evaluate the test split **once**. Models trained on synthetic data are flagged and cannot be promoted in production.

## 📊 Results

### v3 at a glance (2026-11-10)

Default model [`model-bilstm_attn-20261110T162800Z-s7`](https://github.com/nvaltryek-001/ISL-NOVA/releases/tag/model-bilstm_attn-20261110T162800Z-s7): BiLSTM with attention pooling, chosen by **validation** macro-F1 among 15 new models (TCN, Transformer, BiLSTM-attention, LSTM, with and without an `__other__` class, 3 seeds each), 5 ensembles and the v2 model ([run 42851786127](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42851786127)). Write-up: [research/V3_MODELS.md](research/V3_MODELS.md).

| Measured | v1 | v2 | **v3** | Target |
|---|---:|---:|---:|---|
| Test top-1 / top-5 (635 videos) | 91.7 % / 98.3 % | 92.0 % / 98.7 % | **95.1 % / 99.4 %** | — |
| Test macro-F1 · ECE | 91.7 % · 0.027 | 91.6 % · 0.015 | **94.1 % · 0.013** | — |
| Browser pipeline, 73 held-out clips | 74.0 % | 83.6 % | **84.9 %** ([run](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42859291767)) | ≥ 85 % — **not met** (1 clip) |
| *recognized* answers that were correct (browser) | 45/48 | 49/54 | **49/50** | — |
| Unknown signs accepted (shipped rule) | 29.3 % | 34.0 % | **8.8 %** (part B) | < 10 % — **met** |
| Known signs held back (shipped rule) | 12.1 % | — | **13.2 %** (part B) | ≤ 15 % — **met** |
| On-device (browser) model | — | — | ✅ matches server, 24/24 | — |

**v4 (face features)** was trained and evaluated too: see [research/V4_FACE_FEATURES.md](research/V4_FACE_FEATURES.md); the default stays the v3 model.

v1/v2 unknown-sign figures use all 62 out-of-vocabulary glosses; v3 uses the 31 glosses of part B, which were never used to fit or choose anything. The best ensemble reached 97.2 % test top-1 but tied with the selected model on validation, so it was not chosen.

### v2 at a glance (2026-11-10)

Default model [`model-lstm-20261110T111537Z-s7`](https://github.com/nvaltryek-001/ISL-NOVA/releases/tag/model-lstm-20261110T111537Z-s7): the same LSTM, trained with landmark sequences that simulate 8–30 fps, cropped starts/ends and missed hand detections. Same data, split and features as v1; selected by **validation** score. Model card: [docs/MODEL_CARD.md](docs/MODEL_CARD.md).

| Measured | v1 (`…041414Z-s13`) | **v2 (`…111537Z-s7`)** | Run |
|---|---:|---:|---|
| Test top-1 / top-5 (635 videos) | 91.7 % / 98.3 % | **92.0 % / 98.7 %** | [42804474143](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42804474143) |
| Test top-1, mean ± std over 3 seeds | 90.6 ± 0.9 % (baseline recipe) | **93.0 ± 0.7 %** | same |
| Calibration error (ECE) | 0.027 | **0.015** | same |
| **Browser pipeline**, 73 held-out clips as a virtual webcam | 74.0 % | **83.6 %** (target ≥ 85 %: not met) | [42807661120](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42807661120) |
| Unknown-sign AUROC | 0.900 | **0.918** | [42807661840](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/42807661840) |
| Unknown signs *recognized* at the shipped τ | **29.3 %** | 34.0 % ⚠️ | same |
| Best detector (combined), ~10 % false rejection | FAR 17.8 % | **FAR 13.7 %** (target < 10 %: not met) | same |
| Practice Coach: same-sign vs other-sign similarity | — | median 93 vs 13 (own sign higher in 88 % of pairs) | local, 120 test recordings |

Full write-ups: [FPS_ROBUSTNESS.md](research/FPS_ROBUSTNESS.md) · [OPEN_SET_V2.md](research/OPEN_SET_V2.md) · [RESULTS.md](research/RESULTS.md). Everything below this point describes the v1 evaluation in detail.


**Genuine results** from GitHub Actions run [41771084083](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41771084083) on data run [41764539272](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41764539272): dataset `include-official-v1`, 200 classes, INCLUDE official train/val/test split, contract `isl-nova-fc-1.0.0`, seed 13.

### Model comparison (held-out test split, 635 videos)

| Model | Val macro-F1 | Test top-1 | Test top-5 | Precision (macro) | Recall (macro) | Macro-F1 | Weighted-F1 | ECE | Latency / sample | Size |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **LSTM** ✅ selected | 91.1 % | **91.7 %** | **98.3 %** | **93.0 %** | **92.4 %** | **91.7 %** | **91.5 %** | 0.027 | 0.73 ms | 1.78 MB |
| Logistic regression | 88.1 % | 89.1 % | 98.3 % | 90.4 % | 89.9 % | 88.8 % | 88.9 % | 0.024 | 0.02 ms | 0.99 MB |
| GRU | 86.7 % | 86.5 % | 97.6 % | 88.0 % | 87.4 % | 86.1 % | 85.8 % | 0.017 | 0.17 ms | 1.44 MB |
| DTW 1-NN | 80.7 % | 84.4 % | 94.6 % | 85.7 % | 84.8 % | 83.5 % | 83.8 % | 0.040 | 130 ms | 64 MB |

Samples used: 2,448 train / 272 val / 635 test (15 insufficient-input sequences excluded by the contract). Latency is batched model time per sample on a 4-vCPU runner.

**End-to-end check.** The released LSTM loaded through `isl_nova_ml.inference.Predictor` (the code the API uses) reproduced **91.65 % top-1 / 98.27 % top-5** on all 635 test sequences, with 556 *recognized*, 57 *uncertain* and 22 *unknown* answers, **24 ms median** per call including feature extraction (36 ms p95).

<p align="center"><img src="docs/screenshots/ai-laboratory-model.png" alt="AI Laboratory showing the trained LSTM's held-out metrics" width="49%" /> <img src="docs/screenshots/evaluation.png" alt="Per-class F1 and 200-class confusion matrix" width="49%" /></p>

### Unknown signs (open set)

The same model, unchanged, scored **887 recordings of 62 INCLUDE glosses outside the vocabulary**, never used for training, calibration or choosing the threshold (run [41815223675](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41815223675)).

| AUROC | False acceptance (unknown shown as a known sign) | False rejection (known sign not recognized) | Unknown-detection precision / recall | Known recognized **and** correct |
|:---:|:---:|:---:|:---:|:---:|
| **0.900** | **29.3 %** | 12.1 % | 89.1 % / 70.7 % | 84.4 % |

About 3 in 10 signs outside the vocabulary are mapped confidently to a known sign, so the UI always shows the top-5 alternatives and the decision state and never speaks a result on its own. Raising τ to 0.80 lets through 17 % of unknown signs instead, at the cost of rejecting 18 % of known signs. Full sweep: [research/OPEN_SET_EVALUATION.md](research/OPEN_SET_EVALUATION.md).

### From raw video and through the browser

* **Raw video → server-side MediaPipe → model:** 67 of 73 held-out INCLUDE test videos (91.8 %) top-1 correct.
* **In-browser MediaPipe in CI Chromium:** bundle loads in 52–85 ms, hand model on GPU in 0.2–0.7 s and CPU in 0.4 s; the Live page is ready in about 10 s ([run 41815175935](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41815175935)).
* **Virtual-camera replay through the real Live page** ([run 41860050670](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41860050670)): 73 held-out INCLUDE test clips were played into headless Chromium as its webcam. Each went through in-browser MediaPipe, the capture button, `POST /predict/sequence` and the released model.

  | Clips | Top-1 | Top-5 | *recognized* answers that were correct | States | Same clips, offline Python | Hand tracking |
  |:---:|:---:|:---:|:---:|:---:|:---:|:---:|
  | 73 / 73 completed | **74.0 %** (54) | 89.0 % | **45 / 48** (93.8 %) | 48 recognized · 17 uncertain · 8 unknown | 91.8 % | ~10 fps, CPU delegate |

  The gap to the offline figure is mostly frame rate: the 2-vCPU runner has only software WebGL, so MediaPipe ran at ~1 fps on the GPU delegate. The app now switches to the CPU delegate on its own (shown as a badge), which gave ~10 fps instead of the clips' 25 fps. This is a **replay of recorded videos, not a person in front of a webcam**, and uses the same signers as training.

> [!WARNING]
> **What these numbers do not show.** INCLUDE has no signer IDs, so this is **not** signer-independent and says nothing about unseen signers. All signers come from one school in Chennai. Many classes have 1–4 test videos, so per-class scores are noisy. **Live webcam accuracy with a real person has not been measured.** The new-signer workflow exists, but no new-signer recordings exist yet.

Artifacts: model release [`model-lstm-20261104T041414Z-s13`](https://github.com/nvaltryek-001/ISL-NOVA/releases/tag/model-lstm-20261104T041414Z-s13) (weights, SHA-256, comparison, verification, open-set report, 24-sequence test sample). Model card: [docs/MODEL_CARD.md](docs/MODEL_CARD.md) · [research/RESULTS.md](research/RESULTS.md).

## 🧪 Implemented vs tested

| Capability | Implemented | How it was tested | Evidence |
|---|:---:|---|---|
| 200-class recognition (INCLUDE official split) | ✅ | Genuine held-out test split, evaluated once | 91.7 % top-1 · [run 41771084083](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41771084083) |
| Production inference path (`Predictor`, API) | ✅ | 635 test sequences re-run; 24 held-out samples through `POST /predict/sequence` in CI, on Windows **and against the live demo** | 91.65 % · 24/24 · [smoke run](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41861458853) |
| Unknown-sign rejection | ✅ | 887 out-of-vocabulary recordings (62 glosses) | AUROC 0.900, **29.3 % false acceptance** |
| Raw video → MediaPipe → model | ✅ | 73 held-out test videos, server-side extraction | 67/73 (91.8 %) |
| In-browser MediaPipe (GPU/CPU) | ✅ | CI Chromium: bundle, WASM, hand model on GPU and CPU, fps badge | [run 41815175935](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41815175935) |
| Browser capture flow on held-out video (virtual camera) | ✅ | 73 held-out clips played as Chromium's webcam through the Live page, in-browser MediaPipe, API and model | **74.0 % top-1**, 89.0 % top-5; 45/48 *recognized* answers correct · [run 41860050670](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41860050670) |
| Live webcam with a real person | ✅ | ⛔ **Not tested.** No camera or person in any build environment | — |
| Accuracy on new signers | ✅ workflow | ⛔ **No data.** Code path tested with synthetic recordings only | `test_new_signer_evaluation_run` |
| Linguistic verification of 200 signs | ✅ workflow | API + E2E; **0 signs verified**, no approvals made | [protocol](docs/VERIFICATION_PROTOCOL.md) |
| RBAC, consent, four-eyes review, erasure, CRUD | ✅ | pytest on SQLite + PostgreSQL 16, E2E | CI |
| Responsive + accessibility basics | ✅ | E2E: 11 routes × 360/768/1280 px + wide font; labels, alt, names, landmarks | CI |
| Windows local setup | ✅ | `setup_windows.ps1`, `start_windows.ps1`, `test_windows.ps1` on a Windows runner (PowerShell 5.1) | [workflow](https://github.com/nvaltryek-001/ISL-NOVA/actions/workflows/windows-local.yml) |
| Free-tier deployment with model | ✅ | Read-only smoke test from GitHub Actions | [isl-nova.onrender.com](https://isl-nova.onrender.com) |
| **v2** · Hindi / Kannada interface and 200 draft meanings | ✅ | unit test (≥ 90 % string coverage, measured 100 %), API tests, E2E language switch | drafts only; **0 linguist-verified** |
| **v2** · Frame-rate-robust model | ✅ | 3 seeds on the test split; virtual-camera replay | 92.0 % test, **83.6 % browser** |
| **v2** · Unknown-sign detector comparison | ✅ | disjoint unknown glosses for tuning vs evaluation | combined AUROC 0.932; **not shipped in the Predictor yet** |
| **v2** · Practice Coach scoring | ✅ | pytest + E2E (camera gated); 120 test recordings locally | own vs other median 93 vs 13 |
| **v2** · Text-to-Sign, Conversation mode | ✅ | E2E for Text-to-Sign; Conversation: unit/E2E of the page, **speech recognition not testable headless** | — |
| **v2** · Installable PWA, offline shell | ✅ | E2E: manifest, service worker, offline reload, offline badge | — |
| **v2** · Vocabulary proposals (toward 500) | ✅ | pytest: duplicates refused, linguist accept/reject, drafts created | — |
| **v2** · Sign out everywhere, reset codes, TOTP 2FA | ✅ | pytest (RFC 6238 vectors, replay refused) + E2E for all three | — |
| **v2** · Retention job, Prometheus `/metrics` | ✅ | pytest (dry run, apply, counts; metrics format) | — |
| **v2** · Automated accessibility scan | ✅ | axe-core WCAG 2.1 A/AA, 18 routes × light/dark; 0 serious/critical after fixes | CI |
| **v3** · TCN, Transformer, BiLSTM-attention, ensembles, `__other__` class | ✅ | gradient checks; 15 models × held-out test; ensembles | BiLSTM-attention 95.1 % ([V3_MODELS.md](research/V3_MODELS.md)) |
| **v4** · Face (non-manual) features, contract 2.0.0 | ✅ | Python ↔ TypeScript parity fixture; full re-extraction; 10 models × held-out test | mixed: +0.7 to +1.3 points for attention models, −0.9 for TCN ([write-up](research/V4_FACE_FEATURES.md)) |
| **v3** · Unknown-sign detector in server and browser | ✅ | fit on val + part A2, evaluated once on part B | FAR 8.8 %, FRR 13.2 % |
| **v3** · On-device / offline recognition, ONNX export | ✅ | TS vs Python parity (1e-8), 24/24 E2E agreement; onnxruntime parity in CI | — |
| **v3** · Teacher classes, analytics, spaced repetition, pause segmentation | ✅ | pytest, unit, E2E | — |
| **v3** · Refresh tokens, Redis, S3 storage, worker, Grafana, load test | ✅ | CI against real Redis + S3 server; load test 2 vCPU | ~90 req/s, 0 errors |
| Live webcam / new signers / user study | ✅ tooling | ⛔ **not run** — needs people ([protocol](research/USER_STUDY_PROTOCOL.md)) | — |

## 🚀 Quick start

**Requirements:** Python 3.11+ (3.13 recommended), Node.js 20+ (22 recommended), Git, and a recent Chrome, Edge, Firefox or Safari for the camera. PostgreSQL and Docker are optional.

**Linux / macOS**

```bash
git clone https://github.com/nvaltryek-001/ISL-NOVA.git && cd ISL-NOVA
git checkout feat/isl-nova-v2

python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-dev.txt
(cd frontend && npm install && npm run build)

export PYTHONPATH=backend:ml
export BOOTSTRAP_ADMIN_EMAIL=you@example.org BOOTSTRAP_ADMIN_PASSWORD='a-long-password'
python scripts/fetch_model.py --tag model-bilstm_attn-20261110T162800Z-s7 --registry artifacts/models --promote
uvicorn app.main:app --app-dir backend --port 8000
```

Open <http://localhost:8000>, sign in with the bootstrap admin and go to **Live Recognition**. API docs: <http://localhost:8000/api/docs>. Run `cd frontend && npm run dev` in a second terminal to rebuild the client on change.

## ⚡ One-command install (everything)

One script sets up **everything** in a single run: packages, the frontend build, `.env`, the database, the trained model, the MediaPipe files and the INCLUDE dataset. It then checks recognition end to end, and can train and start the app. It was checked on **Windows, Ubuntu and macOS** runners ([run 41977728731](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41977728731)): 24/24 held-out sequences, and logistic regression trained to 89.1–89.3 % top-1.

**Windows (PowerShell):**
```powershell
git clone https://github.com/nvaltryek-001/ISL-NOVA.git ; cd ISL-NOVA ; git checkout feat/isl-nova-v2
powershell -ExecutionPolicy Bypass -File scripts\install_all_windows.ps1 -Start
#   add -Train lstm-fps (the v2 recipe), -Train lstm or -Train all to also train; -SkipDataset to skip the 176 MB download
```

**Linux / macOS (bash):**
```bash
git clone https://github.com/nvaltryek-001/ISL-NOVA.git && cd ISL-NOVA && git checkout feat/isl-nova-v2
bash scripts/install_all.sh --start          # --train lstm-fps | lstm | all · --skip-dataset · --port 8080
bash scripts/start.sh                        # later starts
```

## 🪟 Windows setup

Three PowerShell scripts do everything from the repository root. They are tested on a GitHub Windows runner with **Windows PowerShell 5.1** ([workflow](.github/workflows/windows-local.yml)) and work in PowerShell 7 too. No path is hard-coded, so the repository can live on any drive.

**Prerequisites:** [Python 3.13](https://www.python.org/downloads/windows/) (tick *Add python.exe to PATH*), [Node.js 22 LTS](https://nodejs.org/), [Git for Windows](https://git-scm.com/download/win). Optional: PostgreSQL 16, Docker Desktop.

```powershell
# 1. get the code
git clone https://github.com/nvaltryek-001/ISL-NOVA.git
cd ISL-NOVA
git checkout feat/isl-nova-v2        # later: git pull

# 2. one-time setup: .venv, Python + npm packages, frontend build, .env (random secret,
#    local admin), SQLite database, trained model download (SHA-256 verified)
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
#   options: -WithMediaPipeTasks (server-side video analysis) · -SkipModel · -SkipFrontend
#            -AdminEmail me@example.org · -Python "py -3.13"

# 3. start (opens http://127.0.0.1:8000; Ctrl+C to stop)
powershell -ExecutionPolicy Bypass -File scripts\start_windows.ps1
#   options: -Port 8080 · -Dev (rebuild the frontend on change) · -NoBrowser

# 4. tests
powershell -ExecutionPolicy Bypass -File scripts\test_windows.ps1              # lint, pytest, tsc, unit
powershell -ExecutionPolicy Bypass -File scripts\test_windows.ps1 -E2E -WithModel   # + browser E2E with the model

# 5. download the processed INCLUDE dataset (176 MB of landmarks, no sign-in) and train locally
powershell -ExecutionPolicy Bypass -File scripts\train_windows.ps1                  # LSTM (released recipe)
powershell -ExecutionPolicy Bypass -File scripts\train_windows.ps1 -Model all       # LSTM, GRU, LogReg, DTW
powershell -ExecutionPolicy Bypass -File scripts\train_windows.ps1 -Promote         # make the new model active

# 6. check recognition through your running server (24 held-out INCLUDE sequences)
.\.venv\Scripts\python.exe scripts\check_predictions.py --base http://127.0.0.1:8000
```

The admin email is printed by the setup and its generated password is stored in `.env` (`BOOTSTRAP_ADMIN_PASSWORD`, git-ignored). Change it after the first login. The camera needs `http://localhost` or `http://127.0.0.1` (a secure context), which the start script uses. Setup needs network access to pypi.org, registry.npmjs.org and github.com; the browser loads MediaPipe from cdn.jsdelivr.net and storage.googleapis.com at run time.

## 🗄 Database setup

The app creates and migrates its database on start; no existing data is needed. An empty database is seeded with the 200 vocabulary slots.

| | SQLite (default) | PostgreSQL 16 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./storage/isl_nova.db` | `postgresql://islnova:PASSWORD@localhost:5432/islnova` |
| Create | automatic | `createdb islnova` (or `docker compose up db`) |
| Migrate | `python -m app.migrate` (also on every start) | same |
| Status | `python -m app.migrate --status` | same |
| DDL | — | `python -m app.migrate --render postgresql` |
| Backup | copy the `.db` file while the server is stopped | `pg_dump -Fc islnova > islnova.dump` · restore: `pg_restore -d islnova islnova.dump` |

Migrations are versioned and checksummed (an edited migration is refused) and each runs in a transaction. They are additive; to undo one, restore a backup. Schema: [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md).

## 📦 Model installation

The trained model is **not** committed to Git. It is published as a GitHub pre-release and installed with a checksum check:

```bash
python scripts/fetch_model.py --tag model-bilstm_attn-20261110T162800Z-s7 --registry artifacts/models --promote
```

This downloads the tarball and its `.sha256`, verifies both, unpacks path-safely, verifies the weights hash, registers and promotes the model, and runs a load check with the production `Predictor`. Restart the server to load it. In Docker, set `ISL_NOVA_MODEL_TAG` and the entrypoint does this at start-up. Rollback: `POST /api/v1/models/rollback` (admin) or *AI Laboratory → Registry*.

## 🧬 Dataset import and training

**Reproduce the published model on GitHub Actions (no local download).** Push a run branch; settings live in `ml/runs/*.json`:

| Workflow | Trigger branch | What it does |
|---|---|---|
| `include-data.yml` | `run/include-data` | Preflight (resources, Zenodo record, licence, vocabulary), MD5-verified download, MediaPipe extraction in parallel, merge; raw video is deleted on the runner |
| `include-train.yml` | `run/include-train` | LSTM, GRU, LogReg and DTW in parallel; select on validation; verify with `Predictor`; publish a pre-release |
| `include-open-set.yml` | `run/include-open-set` | Known test split vs out-of-vocabulary glosses |
| `include-live-eval.yml` | `run/include-live-eval` | Held-out clips as Chromium's virtual webcam through the Live page |
| `deploy-smoke.yml` | `run/deploy-smoke` | Read-only checks of a running deployment |
| `windows-local.yml` | `run/windows-check` | The Windows setup, start and test scripts |

**Train locally on the processed landmarks (recommended).** `scripts/train_local.py` (Windows wrapper: `scripts\train_windows.ps1`) downloads the 3,370 landmark sequences that the data workflow extracted from the published release [`dataset-include-landmarks-v1`](https://github.com/nvaltryek-001/ISL-NOVA/releases/tag/dataset-include-landmarks-v1) (176 MB, no sign-in, SHA-256 verified; derived from INCLUDE under CC BY 4.0, attribution inside, no video). It then trains with the same configs, official split and validation-only selection as CI and prints a comparison table. New models are registered but **not promoted** unless you pass `--promote`. Offline? Pass `--data <folder>` with an unzipped copy.

```bash
python scripts/train_local.py --model lstm          # or gru, pooled-logreg, dtw-1nn, all; --promote
```

Checked on a Windows runner ([run 41961463214](https://github.com/nvaltryek-001/ISL-NOVA/actions/runs/41961463214)): `train_windows.ps1 -Model pooled-logreg` downloaded the landmarks and trained in 4.7 minutes, reproducing the CI result exactly (89.1 % top-1, 98.3 % top-5, 88.8 % macro-F1). On a Linux machine the same command gave 89.3 % / 98.3 % / 88.9 %: expect small differences between computers. The LSTM took about 8.5 minutes on a 4-vCPU Linux runner in CI; expect similar or longer on a laptop.

**Or from the raw INCLUDE videos** on your disk:

```bash
# 1. INCLUDE videos (56.8 GB): https://zenodo.org/records/4010759
#    MediaPipe hand_landmarker.task + pose_landmarker_lite.task (setup_windows.ps1 -WithMediaPipeTasks downloads them)
PYTHONPATH=ml python -m isl_nova_ml.include_import --include-root /data/INCLUDE \
  --out data/processed/include --hand-model models/hand_landmarker.task \
  --pose-model models/pose_landmarker_lite.task            # review, then re-run with --approve

# 2. train (also: ml/configs/gru.json, pooled-logreg.json, dtw-1nn.json)
PYTHONPATH=ml python -m isl_nova_ml.train --config ml/configs/lstm_baseline.json \
  --manifest data/processed/include/manifest.json --data-root data/processed/include \
  --registry artifacts/models --dataset-version include-official-v1

# 3. review artifacts/models/<id>/metrics.json, then promote in AI Laboratory → Registry
```

Recordings collected in the app train through *AI Laboratory → Experiments* on a frozen dataset version. The pipeline enforces approval, licence and consent, aborts on split leakage, and writes top-1/top-5, macro/weighted F1, per-class report, confusion matrix, ECE, open-set AUROC, per-signer accuracy, latency and size.

> [!NOTE]
> `python -m isl_nova_ml.smoke` trains on **procedurally generated, non-ISL** trajectories to check the code. Those models are flagged `synthetic`, use class IDs `SYN…`, and cannot be promoted in production.

## ✅ Testing

| Suite | Command | Last result |
|---|---|---|
| Lint | `ruff check backend ml dataset/scripts scripts` | ✅ pass |
| Backend + ML | `pytest -q` | ✅ **60 passed**, 1 skipped (needs a MediaPipe model file); Linux **and Windows** |
| Backend on PostgreSQL 16 | `TEST_DATABASE_URL=postgresql://… pytest backend/tests` | ✅ pass (CI) |
| Frontend types | `cd frontend && npm run typecheck` | ✅ pass |
| Frontend unit + Python↔TS feature parity | `npm test` | ✅ **17 passed** |
| End-to-end (Chromium) | `npm run build && npm run e2e` | ✅ **19 passed**: 16 app + 3 with the real model (24/24 held-out samples) |
| Docker image + container health | CI `docker` job | ✅ pass |
| Deployed instance (read-only) | `deploy-smoke.yml` | ✅ health, CSP/HSTS, model, **24/24** via the live API, in-browser MediaPipe (GPU) at 1280 and 390 px |

The end-to-end suite covers sign-up, login and RBAC (an admin page refused to a learner); search, sign create/edit/retire/restore and bookmarks; the linguist checklist flow; signer → consent → recording upload → annotation → second-reviewer approval; model-unavailable and camera-denied states; kiosk; every route for one `h1` and no unnamed buttons; light/dark themes; and layout and accessibility at 360, 768 and 1280 px. Bugs the tests caught: [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md).

## 🐳 Docker

```bash
# app + PostgreSQL 16 (set JWT_SECRET, POSTGRES_PASSWORD, BOOTSTRAP_ADMIN_* in .env first)
cp .env.example .env
docker compose up --build

# or the app alone, with the trained model installed at start-up
docker build -t isl-nova .
docker run -p 8000:8000 -e ISL_NOVA_ENV=production -e JWT_SECRET=$(openssl rand -hex 32) \
  -e CORS_ORIGINS=http://localhost:8000 -e ISL_NOVA_MODEL_TAG=model-bilstm_attn-20261110T162800Z-s7 isl-nova
```

Optional services for several API processes and monitoring (see the comments in [`docker-compose.yml`](docker-compose.yml)):

```bash
docker compose --profile scale --profile monitoring up --build   # + Redis, job worker, S3 storage, Prometheus, Grafana (:3000)
```

The multi-stage [`Dockerfile`](Dockerfile) builds the SPA and the API into one image running as a non-root user. [`scripts/docker-entrypoint.sh`](scripts/docker-entrypoint.sh) applies migrations, installs the model named by `ISL_NOVA_MODEL_TAG` (SHA-256 verified; a failed download is logged and the API reports `model_unavailable`), and serves on `$PORT`.

## 🌐 Deployment and live demo

**[https://isl-nova.onrender.com](https://isl-nova.onrender.com)** runs the Docker image on Render's **free plan** (no paid resources), with the released LSTM installed at start-up.

* The first request after ~15 minutes idle takes about a minute while the instance wakes.
* The demo database is **temporary** and reset on every restart or redeploy. Register as a learner to try Live Recognition, Sign Explorer, Communication and the Academy. There is no admin account on the demo.
* Render does not receive push webhooks for this repository, so a new commit goes live only after a manual deploy.
* Please **do not upload recordings of real signers** to the demo.

Persistent deployments (disk or managed PostgreSQL, Fly.io, Railway), HTTPS/CORS, a post-deploy checklist and rollback: [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md).

## 🔌 API

84 operations under `/api/v1`, generated into [docs/API_CONTRACT.md](docs/API_CONTRACT.md) from the code and served live at `/api/v1/openapi.json` and `/api/docs`.

<details><summary><b>Highlights</b></summary>

```text
GET    /health                         POST /auth/register · /auth/login · GET/PATCH /me
GET    /signs?q=&category=&status=     GET /signs/{id}   POST /signs   PATCH /signs/{id}
DELETE /signs/{id} (retire)            POST /signs/{id}/review   PUT /signs/{id}/translations/{lang}
GET    /signs/review-sheet.csv (linguists)
POST   /predict/sequence               GET /model/info · /model/metrics
GET    /dataset/stats · /dataset/signs POST /dataset/recordings (multipart) · /dataset/validate
POST   /dataset/signers · /dataset/signers/{id}/consents · /dataset/consents/{id}/revoke
GET    /annotations  POST /annotations  PATCH /annotations/{id}
GET/POST /dataset/versions             GET /dataset/versions/{id}/manifest
GET/POST /experiments  POST /experiments/{id}/run   GET /models  POST /models/{id}/promote · /models/rollback
GET    /evaluation/metrics · /evaluation/confusion-matrix   POST/GET /evaluation/runs (new signers)
GET    /history  POST /feedback  GET /learning/progress  POST /learning/attempts  GET /learning/quiz
```

```bash
curl -s http://localhost:8000/api/v1/model/info
curl -s -X POST http://localhost:8000/api/v1/predict/sequence -H 'Content-Type: application/json' \
     -d '{"frames": [...], "aspect": 1.78, "top_k": 5}'
```
</details>

## ⚙️ Environment variables

Copy [`.env.example`](.env.example) to `.env` (the Windows setup does this for you). Never commit `.env`.

| Variable | Purpose | Default |
|---|---|---|
| `ISL_NOVA_ENV` | `production` enforces a strong secret, no synthetic models, no wildcard CORS, HSTS | `development` |
| `DATABASE_URL` | `sqlite:///…` or `postgresql://user:pass@host/db` | SQLite in `storage/` |
| `JWT_SECRET` | ≥ 32 random characters (required in production) | ephemeral in development |
| `JWT_TTL_MINUTES` | token lifetime | 120 |
| `CORS_ORIGINS` | comma-separated origins | `http://localhost:5173,http://localhost:8000` |
| `STORAGE_DIR` / `MODEL_REGISTRY_DIR` | object storage and model registry | `storage/objects`, `artifacts/models` |
| `BOOTSTRAP_ADMIN_EMAIL` / `_PASSWORD` | ensure an admin exists at start-up | - |
| `ALLOW_OPEN_REGISTRATION` | allow self sign-up as learner | `true` |
| `MAX_UPLOAD_MB`, `ANALYSIS_RETENTION_HOURS` | upload limit, analysis retention | 50, 24 |
| `VOCABULARY_LIMIT` | fixed vocabulary size (creating or accepting signs beyond it is refused; 0 = no limit) | 200 |
| `REFRESH_TTL_DAYS` | refresh-token lifetime | 30 |
| `STORAGE_BACKEND`, `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION` | `local` or `s3` (any S3-compatible service) | local |
| `REDIS_URL` | shared rate limit and job queue (run `python -m app.worker` for jobs) | unset |
| `RETENTION_INTERVAL_HOURS`, `HISTORY_RETENTION_DAYS`, `NOTIFICATION_RETENTION_DAYS` | retention job interval (0 = off); history age limit (0 = keep); read-notification age limit | 24, 0, 180 |
| `METRICS_TOKEN` | bearer token for `/metrics` from outside localhost | unset |
| `RATE_LIMIT_PER_MINUTE`, `AUTH_RATE_LIMIT_PER_MINUTE` | per-IP limits | 120, 10 |
| `PBKDF2_ITERATIONS` | password hashing cost | 600000 |
| `ISL_NOVA_HAND_MODEL`, `ISL_NOVA_POSE_MODEL` | MediaPipe `.task` files for server-side video analysis | - |
| `ISL_NOVA_MODEL_TAG` | Docker: install this model release at start-up | - |
| `ISL_NOVA_GENERATE_JWT_SECRET` | Docker demo only: generate an ephemeral secret | - |

## ⚠️ Limitations

* Results are on INCLUDE's **official split, not signer-independent**; INCLUDE has no signer IDs and all signers come from one school.
* **Unknown signs**: 8.8 % of unseen out-of-vocabulary signs are still accepted as a vocabulary sign (held-out glosses; v1: 29 %).
* **Browser pipeline** reaches 84.9 % on held-out clips, one clip short of the 85 % target.
* **No real-person webcam test** and **no new-signer accuracy** yet.
* **0 / 200 signs linguistically verified**; the INCLUDE gloss is a label, not a reviewed ISL description.
* Category gaps (few everyday verbs; no food or question words).
* Isolated signs only: no grammar or translation (Conversation shows a *recognized word sequence*). Face (non-manual) features exist as contract 2.0.0 but are not in the default model.
* CPU NumPy models; the free demo sleeps when idle and loses its data on restart.
* Not yet tested with Deaf users.

Full list: [research/LIMITATIONS.md](research/LIMITATIONS.md).

## 🔬 Research opportunities

* **Signer-independent evaluation** with consented, signer-labelled recordings ([protocol](research/SIGNER_INDEPENDENT_PROTOCOL.md)).
* **Unknown-sign detection** on new signers and everyday non-sign movement ([v3 results](research/V3_MODELS.md)).
* **Feature ablations** and larger models ([ablation plan](research/ABLATION_STUDY.md)).
* **Robustness** to lighting, background, distance and camera quality.
* **Non-manual features** for phrases and grammar ([v4 face results](research/V4_FACE_FEATURES.md)) and continuous signing.
* **Linguistic resources**: verified Hindi/Kannada meanings and regional variants.

Questions, protocols and a paper outline: [research/](research/).

## 📁 Repository structure

```text
backend/app/            API: framework, routers, db, migrations, security, services
backend/tests/          API, RBAC, CRUD, dataset, consent, evaluation, inference-state tests
ml/isl_nova_ml/         feature contract, models, training, registry, inference, INCLUDE pipeline
ml/configs/  ml/runs/   experiment configs · settings for the staged Actions workflows
ml/tests/               contract, gradients, splits/leakage, registry, open set, parity fixture
frontend/src/           React app: pages/, components/, lib/ (api, query, router, store, features, landmarks)
frontend/tests/         unit + parity tests, Playwright E2E, live-eval and deploy smoke scripts
dataset/                vocabulary CSVs, manifests, INCLUDE label map + splits, generator
docs/  research/        architecture, API, schema, protocols, model card, deployment, status · research
scripts/                setup/start/test_windows.ps1, fetch_model.py, check_predictions.py, entrypoint, API-doc generator
.github/workflows/      CI and the staged data/train/evaluation/deployment/Windows workflows
```

## 📜 Licence and attribution

**No licence has been chosen for this repository yet.** Until the owner adds a `LICENSE` file, default copyright applies.

* Vocabulary glosses, split lists and the trained model's data derive from **INCLUDE** by A. Sridhar, R. G. Ganesan, P. Kumar and M. Khapra (AI4Bharat, IIT Madras): dataset **CC BY 4.0**, code and label maps MIT ([`dataset/sources/include/`](dataset/sources/include/)). The INCLUDE videos are not redistributed here.
* MediaPipe (Google) is loaded at run time under its own licence.

## 👥 Contributors

* **[nvaltryek-001](https://github.com/nvaltryek-001)**: project owner.
* Built with **Claude** (Anthropic) as the AI pair programmer.
* INCLUDE dataset authors (see above), whose data made the model possible.

Contributions are welcome: read [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md). In short: no invented data or metrics, the linguist role only for qualified ISL reviewers, never commit media or weights, and all checks must pass. Roadmap: [docs/DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md).

## 📚 References

* Sridhar, A., Ganesan, R. G., Kumar, P., Khapra, M. (2020). *INCLUDE: A Large Scale Dataset for Indian Sign Language Recognition.* ACM Multimedia. [doi:10.1145/3394171.3413528](https://doi.org/10.1145/3394171.3413528)
* Joshi, A. et al. (2024). *iSign: A Benchmark for Indian Sign Language Processing.* Findings of ACL. [doi:10.18653/v1/2024.findings-acl.643](https://doi.org/10.18653/v1/2024.findings-acl.643)
* Hochreiter, S., Schmidhuber, J. (1997). *Long Short-Term Memory.* Neural Computation 9(8). [doi:10.1162/neco.1997.9.8.1735](https://doi.org/10.1162/neco.1997.9.8.1735)
* Guo, C. et al. (2017). *On Calibration of Modern Neural Networks.* ICML. [arXiv:1706.04599](https://arxiv.org/abs/1706.04599)
* Hendrycks, D., Gimpel, K. (2017). *A Baseline for Detecting Misclassified and Out-of-Distribution Examples.* ICLR. [arXiv:1610.02136](https://arxiv.org/abs/1610.02136)
* Lugaresi, C. et al. (2019). *MediaPipe: A Framework for Building Perception Pipelines.* [arXiv:1906.08172](https://arxiv.org/abs/1906.08172)

Full BibTeX: [research/REFERENCES.bib](research/REFERENCES.bib).

<div align="center"><sub>ISL NOVA · v2.0.0-dev · branch <code>feat/isl-nova-v2</code></sub></div>
