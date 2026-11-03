# Deployment guide

**Status: not deployed.** No hosting credentials were provided, and none were created. No paid resources were provisioned. There is no live URL.

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

Any container host works. Example, Render (no `render.yaml` is committed, to avoid accidental provisioning):

1. Create a **PostgreSQL 16** instance and copy its internal URL.
2. Create a **Web Service** from this repository using the `Dockerfile`, with a persistent disk mounted at `/data`.
3. Set environment variables: `DATABASE_URL`, `JWT_SECRET`, `CORS_ORIGINS=https://<your-domain>`, `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD`, `ISL_NOVA_ENV=production`.
4. Health check path: `/api/v1/health`.

Fly.io / Railway: the same image, a Postgres add-on, a volume at `/data`, and the same variables.

## 3. HTTPS, domain, CORS
Terminate TLS at the platform or a reverse proxy; uvicorn runs with `--proxy-headers`. Set `CORS_ORIGINS` to the exact HTTPS origin. The camera requires a secure context (HTTPS or localhost).

## 4. Object storage and models
The local storage adapter writes to `STORAGE_DIR` (a mounted volume). For S3-compatible storage, implement the four methods of `LocalStorage` (`put/get/exists/delete`). Model artefacts live in `MODEL_REGISTRY_DIR`; copy trained model directories there and promote one in the AI Laboratory.

## 5. Post-deployment checklist
- [ ] `GET /api/v1/health` returns `status: ok`, `migrations.pending: []`
- [ ] SPA routes load (`/`, `/signs`, `/live`) over HTTPS
- [ ] `GET /api/v1/model/info` shows the expected state (`model_unavailable` until a real model is promoted)
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
