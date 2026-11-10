#!/usr/bin/env bash
# ISL NOVA: complete local installation on Linux or macOS in one command.
#
#   bash scripts/install_all.sh                 # everything except training
#   bash scripts/install_all.sh --train lstm    # also train (lstm | gru | pooled-logreg | dtw-1nn | all)
#   bash scripts/install_all.sh --start         # start the app at the end
#   bash scripts/install_all.sh --skip-dataset  # skip the 176 MB dataset download
#
# Steps: prerequisites -> .venv + packages -> frontend build -> .env -> database
# -> trained model (SHA-256 verified) -> MediaPipe task files -> INCLUDE landmark
# dataset -> end-to-end recognition check -> optional training / start.
# Safe to run again. Needs internet access (pypi.org, npmjs.org, github.com,
# storage.googleapis.com). Nothing outside the repository folder is modified.
set -euo pipefail

TRAIN=""; START=0; SKIP_DATASET=0; PORT=8000
MODEL_TAG="model-lstm-20261110T111537Z-s7"
while [ $# -gt 0 ]; do
  case "$1" in
    --train) TRAIN="$2"; shift 2 ;;
    --start) START=1; shift ;;
    --skip-dataset) SKIP_DATASET=1; shift ;;
    --port) PORT="$2"; shift 2 ;;
    -h|--help) sed -n 2,12p "$0"; exit 0 ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
c_ok() { printf '    \033[32mOK\033[0m  %s\n' "$1"; }
step() { printf '\n\033[35m[%s/10] %s\033[0m\n' "$1" "$2"; }
die()  { printf '\n\033[31mERROR\033[0m  %s\n' "$1" >&2; exit 1; }
[ -f backend/app/main.py ] || die "run this from the ISL-NOVA repository"

step 1 "Prerequisites"
PY="${PYTHON:-}"; if [ -z "$PY" ]; then for p in python3.13 python3.12 python3.11 python3; do command -v "$p" >/dev/null && { PY="$p"; break; }; done; fi
[ -n "$PY" ] || die "Python 3.11+ not found (macOS: brew install python@3.13; Ubuntu: sudo apt install python3 python3-venv)"
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || die "Python $("$PY" -V) is too old; 3.11+ required"
c_ok "$("$PY" -V)"
command -v node >/dev/null || die "Node.js 20+ not found (https://nodejs.org/ or: brew install node)"
[ "$(node -p 'process.versions.node.split(".")[0]')" -ge 20 ] || die "Node.js $(node -v) is too old; 20+ required"
c_ok "Node.js $(node -v), npm $(npm -v)"
command -v git >/dev/null && c_ok "$(git --version)" || echo "    note: git not found (only needed for updates)"

step 2 "Python virtual environment and packages"
[ -x .venv/bin/python ] || "$PY" -m venv .venv
VPY="$ROOT/.venv/bin/python"
"$VPY" -m pip install --quiet --upgrade pip
"$VPY" -m pip install --quiet -r backend/requirements-dev.txt
c_ok "packages installed in .venv"

step 3 "Frontend"
( cd frontend && { [ -f package-lock.json ] && npm ci --no-audit --no-fund || npm install --no-audit --no-fund; } && npm run build )
c_ok "frontend/dist built"

step 4 ".env"
if [ ! -f .env ]; then
  SECRET="$("$VPY" -c 'import secrets; print(secrets.token_urlsafe(48))')"
  ADMIN_PW="$("$VPY" -c 'import secrets; print(secrets.token_urlsafe(12))')"
  sed -e "s|^JWT_SECRET=.*|JWT_SECRET=$SECRET|" \
      -e "s|^BOOTSTRAP_ADMIN_EMAIL=.*|BOOTSTRAP_ADMIN_EMAIL=admin@localhost.test|" \
      -e "s|^BOOTSTRAP_ADMIN_PASSWORD=.*|BOOTSTRAP_ADMIN_PASSWORD=$ADMIN_PW|" .env.example > .env
  chmod 600 .env
  c_ok ".env created; admin admin@localhost.test, password in .env (BOOTSTRAP_ADMIN_PASSWORD)"
else
  c_ok ".env already exists; left unchanged"
fi
set -a; . ./.env; set +a
export PYTHONPATH="$ROOT/backend:$ROOT/ml"

step 5 "Database"
"$VPY" -m app.migrate >/dev/null
c_ok "database ready (${DATABASE_URL})"

step 6 "Trained model $MODEL_TAG"
"$VPY" scripts/fetch_model.py --tag "$MODEL_TAG" --registry "${MODEL_REGISTRY_DIR:-artifacts/models}" --promote >/dev/null
c_ok "model installed and promoted"
"$VPY" scripts/fetch_references.py >/dev/null && c_ok "sign references installed (Practice Coach, Text-to-Sign)" \
  || echo "    note: sign references could not be downloaded; Practice Coach will report them missing"

step 7 "MediaPipe task files (server-side Video Analysis)"
mkdir -p artifacts/mediapipe
[ -f artifacts/mediapipe/hand_landmarker.task ] || curl -fsSL -o artifacts/mediapipe/hand_landmarker.task \
  https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
[ -f artifacts/mediapipe/pose_landmarker_lite.task ] || curl -fsSL -o artifacts/mediapipe/pose_landmarker_lite.task \
  https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task
"$VPY" - "$ROOT" <<'PY'
import sys, pathlib
root = pathlib.Path(sys.argv[1]); env = root / ".env"
vals = {"ISL_NOVA_HAND_MODEL": root / "artifacts/mediapipe/hand_landmarker.task",
        "ISL_NOVA_POSE_MODEL": root / "artifacts/mediapipe/pose_landmarker_lite.task"}
lines = [next((f"{k}={v}" for k, v in vals.items() if l.startswith(k + "=")), l) for l in env.read_text().splitlines()]
env.write_text("\n".join(lines) + "\n")
PY
c_ok "task files in artifacts/mediapipe (paths written to .env)"

if [ "$SKIP_DATASET" = 0 ]; then
  step 8 "Processed INCLUDE dataset (176 MB, CC BY 4.0)"
  "$VPY" scripts/train_local.py --download-only
else
  step 8 "Dataset skipped (--skip-dataset)"
fi

step 9 "End-to-end check (24 held-out sequences through a temporary server)"
if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then
  echo "    port $PORT is in use; checking the running server"
  "$VPY" scripts/check_predictions.py --base "http://127.0.0.1:$PORT"
else
  mkdir -p storage
  "$VPY" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "$PORT" > storage/install_check.log 2>&1 &
  SRV=$!
  trap 'kill $SRV 2>/dev/null || true' EXIT
  for _ in $(seq 1 60); do curl -fsS "http://127.0.0.1:$PORT/api/v1/health" >/dev/null 2>&1 && break; sleep 1; done
  "$VPY" scripts/check_predictions.py --base "http://127.0.0.1:$PORT"
  kill $SRV 2>/dev/null || true; trap - EXIT
fi
c_ok "recognition check passed"

if [ -n "$TRAIN" ]; then
  step 10 "Training: $TRAIN"
  "$VPY" scripts/train_local.py --model "$TRAIN"
else
  step 10 "Training skipped (add --train lstm or --train all)"
fi

printf '\n\033[32m================ ISL NOVA is installed ================\033[0m\n'
echo "  Start : bash scripts/start.sh            (http://127.0.0.1:$PORT)"
echo "  Tests : .venv/bin/python -m pytest -q ; (cd frontend && npm test && npm run e2e)"
echo "  Train : .venv/bin/python scripts/train_local.py --model all"
echo "  Login : admin@localhost.test, password = BOOTSTRAP_ADMIN_PASSWORD in .env"
[ "$START" = 1 ] && exec bash scripts/start.sh --port "$PORT"
exit 0
