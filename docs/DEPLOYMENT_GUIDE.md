# Deployment guide

**Status: not deployed.** No hosting credentials were provided, and none were created. No paid resources were provisioned. There is no live URL.

## 0. Local development (Windows, Linux, macOS)

Windows: `scripts\setup_windows.ps1`, then `scripts\start_windows.ps1` (see the README section *Windows setup*). Linux/macOS: the README *Quick start*. Both use SQLite and install the trained model with `scripts/fetch_model.py`. After starting, `python scripts/check_predictions.py --base http://127.0.0.1:8000` sends 24 held-out INCLUDE sequences through your server.

## 1. Local, production-like (Docker Compose)

```bash
cp .env.example .env
# set: JWT_SECRET (python -c "import secrets;print(secrets.token_urlsafe(48))"), POSTGRES_PASSWORD,
#      BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD, CORS_ORIGINS=http://localhost:8000
docker compose up --build
open http://localhost:8000          # health: /api/v1/health, API docs: /api/docs
```

The container runs `python -m app.migrate`, then uvicorn. It seeds roles and the 200-slot vocabulary on first start. Data lives in the `pgdata` and `appdata` volumes.

> Verification status: the image could not be built in the build sandbox (Docker Hub blocked). The container's file layout and production start command were verified outside Docker; the GitHub Actions `docker` job builds the image and checks `/api/v1/health`.

## 2. Managed platforms

### Live demo: Render free plan (deployed)

A public demo runs at **https://isl-nova.onrender.com** (Render web service
`isl-nova`, Docker runtime, free plan, Singapore, branch
`feat/isl-nova-platform`; Render does not receive push webhooks for this repo, so
new commits are deployed with a manual deploy from the dashboard or API). It was created with these environment variables and
**no paid resources**:

| Variable | Value | Why |
|---|---|---|
| `ISL_NOVA_ENV` | `production` | strict config checks, HSTS |
| `ISL_NOVA_MODEL_TAG` | `model-lstm-20261104T041414Z-s13` | entrypoint installs the verified release (SHA-256 checked) at start |
| `ISL_NOVA_GENERATE_JWT_SECRET` | `1` | container generates its own signing key; no secret passes through config or logs |
| `DATABASE_URL` | `sqlite:////data/isl_nova.sqlite` | free plan has no disk and free Postgres expires after 30 days |
| `CORS_ORIGINS` | `https://isl-nova.onrender.com` | same-origin SPA |
| `PBKDF2_ITERATIONS` | `310000` | OWASP minimum; keeps login responsive on 0.1 CPU |

**Free-plan consequences (by design of the plan, not bugs):** the service sleeps
after ~15 min idle and the first request takes ~1 min; the SQLite database and
any accounts or recordings are **wiped on every restart or redeploy**; sessions
end on restart. No bootstrap admin is configured, so the demo has no admin
account; visitors can register as *learners* and use live recognition,
explorer, communication and academy. **Do not upload real signer recordings to
the demo.** For a persistent deployment use a paid disk or managed Postgres
(owner approval required) and set `JWT_SECRET`, `BOOTSTRAP_ADMIN_*`.

Verified after deployment: `GET /api/v1/health` → `status: ok`, model available;
`GET /api/v1/model/info` → `lstm-20261104T041414Z-s13`, 200 classes,
`synthetic: false`; start-up log shows the release installed and promoted with
SHA-256 `e0979cd5…c543c0`. The read-only smoke workflow
(`.github/workflows/deploy-smoke.yml`, push `run/deploy-smoke`) re-checks
health, security headers, the model, 24 held-out landmark sequences through the
production API, and the UI camera pipeline at desktop and phone widths.

### Persistent deployment (Render / Fly.io / Railway)

1. Create a **PostgreSQL 16** instance and copy its internal URL.
2. Create a **Web Service** from this repository using the `Dockerfile`, with a persistent disk mounted at `/data`.
3. Set environment variables: `DATABASE_URL`, `JWT_SECRET`, `CORS_ORIGINS=https://<your-domain>`, `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD`, `ISL_NOVA_ENV=production`, optionally `ISL_NOVA_MODEL_TAG`.
4. Health check path: `/api/v1/health`.

## 3. HTTPS, domain, CORS
Terminate TLS at the platform or a reverse proxy; uvicorn runs with `--proxy-headers`. Set `CORS_ORIGINS` to the exact HTTPS origin. The camera requires a secure context (HTTPS or localhost).

## 4. Object storage and models
The local storage adapter writes to `STORAGE_DIR` (a mounted volume). For S3-compatible storage, implement the four methods of `LocalStorage` (`put/get/exists/delete`). Model artefacts live in `MODEL_REGISTRY_DIR`; copy trained model directories there and promote one in the AI Laboratory.

## 4b. Install the trained model
Set `ISL_NOVA_MODEL_TAG=<release tag>`: `scripts/docker-entrypoint.sh` installs and
promotes that release on start when no model is active (a failed download is
logged and the API reports `model_unavailable`). Or install manually:
```bash
docker compose exec app python /app/scripts/fetch_model.py \
  --tag model-lstm-20261104T041414Z-s13 --registry /data/models --promote
docker compose restart app
```

## 5. Post-deployment checklist
- [ ] `GET /api/v1/health` returns `status: ok`, `migrations.pending: []`
- [ ] SPA routes load (`/`, `/signs`, `/live`) over HTTPS
- [ ] `GET /api/v1/model/info` shows the expected state (`ready` with `lstm-20261104T041414Z-s13` once the trained model is installed)
- [ ] Login works; bootstrap admin password changed; open registration set as intended
- [ ] Response headers include CSP, `X-Frame-Options: DENY`
- [ ] No secrets in logs; `.env` not in the image (`.dockerignore`)

## 6. Rollback
* **Application:** redeploy the previous image tag. Migrations are additive; restore the database from backup if a migration must be undone.
* **Model:** `POST /api/v1/models/rollback` (admin) restores the previously active model.

## Required from the owner to deploy
1. Choice of platform and an account or API token for it.
2. A domain name (optional) and the production `CORS_ORIGINS`.
3. Approval for any paid resources (database, disk).
