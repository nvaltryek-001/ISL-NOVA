#!/bin/sh
# Container start: apply migrations, optionally install a released model, serve.
# ISL_NOVA_MODEL_TAG=<release tag> installs that verified GitHub pre-release into
# MODEL_REGISTRY_DIR when no model is active yet (useful on hosts without a
# persistent disk). Failure to fetch never blocks start-up: the API then reports
# model_unavailable honestly.
set -e
# Single-instance demo hosts with an ephemeral database may let the container
# generate its own signing key (sessions end on restart, as does the data).
if [ -z "${JWT_SECRET:-}" ] && [ "${ISL_NOVA_GENERATE_JWT_SECRET:-}" = "1" ]; then
  JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
  export JWT_SECRET
fi
python -m app.migrate
if [ -n "${ISL_NOVA_MODEL_TAG:-}" ]; then
  if ! python -c "import json,sys,pathlib; r=pathlib.Path('${MODEL_REGISTRY_DIR}')/'registry.json'; sys.exit(0 if r.exists() and json.loads(r.read_text()).get('active') else 1)" 2>/dev/null; then
    python /app/scripts/fetch_model.py --tag "$ISL_NOVA_MODEL_TAG" --registry "$MODEL_REGISTRY_DIR" --promote \
      || echo "WARNING: model $ISL_NOVA_MODEL_TAG could not be installed; recognition will report model_unavailable"
  fi
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
