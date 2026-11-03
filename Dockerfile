# ISL NOVA - single image: API + built web client.

# ---- frontend build ---------------------------------------------------------
FROM node:22.11.0-bookworm-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund --ignore-scripts
COPY frontend/ ./
RUN npm run typecheck && npm test && npm run build

# ---- runtime ----------------------------------------------------------------
FROM python:3.13.1-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/backend:/app/ml ISL_NOVA_ENV=production \
    STORAGE_DIR=/data/objects MODEL_REGISTRY_DIR=/data/models FRONTEND_DIST=/app/frontend/dist
# libgl/libglib are needed by OpenCV/MediaPipe wheels
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 nova && mkdir -p /data && chown nova /data
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt
COPY backend/app backend/app
COPY ml/isl_nova_ml ml/isl_nova_ml
COPY dataset/vocabulary dataset/vocabulary
COPY dataset/sources dataset/sources
COPY --from=web /app/frontend/dist frontend/dist
USER nova
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1
WORKDIR /app/backend
CMD ["sh", "-c", "python -m app.migrate && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
