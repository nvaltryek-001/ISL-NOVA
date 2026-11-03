# Technology stack

| Area | Specified | Implemented | Why |
|---|---|---|---|
| Web framework | FastAPI | **Starlette 1.7 + Pydantic 2.13** with a small typed routing layer (`app/api.py`) that generates OpenAPI | FastAPI was not installable in the build sandbox; Starlette + Pydantic are FastAPI's foundations, so routes port 1:1 if desired |
| DB access / migrations | SQLAlchemy + Alembic | Parameterised SQL through `app/db.py`; **versioned, checksummed SQL migrations** (`app/migrate.py`) rendered per dialect | Not installable; the migration runner detects edited migrations and runs each in a transaction |
| Database | PostgreSQL | **PostgreSQL 16** (production, CI) and SQLite (development, tests) | Schema and all executed statements validated on PostgreSQL 16 |
| Auth | - | PBKDF2-HMAC-SHA256 (600k iterations), PyJWT HS256 | Standard-library hashing, no native deps |
| Frontend | React, Vite, TS, Tailwind | **React 19.2, TypeScript 6 (strict), Tailwind CSS 4.3**, bundled by **esbuild 0.28** (`scripts/build.mjs`) | Vite not installable; esbuild is Vite's own bundler |
| Router / server state / store | React Router, TanStack Query, Zustand | In-house `lib/router.tsx`, `lib/query.ts`, `lib/store.ts` (~250 lines total) | Not installable; same concepts (route params, cache + invalidation + polling, external stores) |
| Charts / motion | Recharts, Framer Motion | Accessible SVG charts (`components/charts.tsx`); CSS animations honouring reduced-motion | Not installable |
| Validation | Zod | **Zod 3.25** (forms) + Pydantic (server) | |
| Frontend tests | Vitest, RTL, Playwright | **node:test** + `react-dom/server` for components; **Playwright 1.63** for E2E | |
| Computer vision | OpenCV, MediaPipe | **MediaPipe Tasks** (browser via jsDelivr, pinned 0.10.14; Python 0.10.32) + **OpenCV 5** for decoding/probing | |
| ML | TensorFlow/Keras, PyTorch | **NumPy** LSTM and GRU with hand-written backprop (gradient-checked), scikit-learn logistic-regression baseline, DTW 1-NN | No DL framework installable; TCN/Transformer documented as next candidates |
| Experiment tracking | MLflow | JSON artefacts per run (`model.json`, `metrics.json`, `training_log.jsonl`) + `experiments` tables | Not installable |
| Infra | Docker, GitHub Actions | Multi-stage `Dockerfile`, `docker-compose.yml` (PostgreSQL 16), CI with SQLite + PostgreSQL tests, E2E and image build | |

Pinned Python versions: `backend/requirements.txt`. Node: `frontend/package.json`.
