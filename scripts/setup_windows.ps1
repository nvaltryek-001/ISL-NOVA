<#
.SYNOPSIS
  One-time local setup of ISL NOVA on Windows (PowerShell 5.1 or 7+).

.DESCRIPTION
  Run from the repository root:
      powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1

  Steps: check prerequisites -> create .venv -> install Python packages ->
  install and build the frontend -> create .env (random JWT secret, local
  admin) -> migrate the SQLite database -> install the trained model from the
  GitHub release (SHA-256 verified) -> optionally download the MediaPipe task
  files for server-side video analysis.

  Needs network access to pypi.org, registry.npmjs.org and github.com (and
  storage.googleapis.com for -WithMediaPipeTasks). Nothing outside the
  repository folder is modified.

.PARAMETER ModelTag
  GitHub release of the trained model to install.
.PARAMETER SkipModel
  Do not download the trained model (recognition will report model_unavailable).
.PARAMETER SkipFrontend
  Skip npm install / build (use if node_modules and frontend\dist already exist).
.PARAMETER WithMediaPipeTasks
  Also download hand_landmarker.task and pose_landmarker_lite.task for the
  server-side Video Analysis module.
.PARAMETER AdminEmail
  Email of the local bootstrap admin written to .env (default admin@localhost.test).
.PARAMETER Python
  Python launcher to use (default: "py -3.13" when available, else "python").
#>
[CmdletBinding()]
param(
  [string]$ModelTag = "model-bilstm_attn-20261110T162800Z-s7",
  [switch]$SkipModel,
  [switch]$SkipFrontend,
  [switch]$WithMediaPipeTasks,
  [string]$AdminEmail = "admin@localhost.test",
  [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok($msg) { Write-Host "    OK  $msg" -ForegroundColor Green }
function Fail($msg) { Write-Host "    ERROR  $msg" -ForegroundColor Red; exit 1 }
function Run($exe, [string[]]$argv, $what) {
  & $exe @argv
  if ($LASTEXITCODE -ne 0) { Fail "$what failed (exit code $LASTEXITCODE)" }
}

if (-not (Test-Path (Join-Path $Root "backend\app\main.py"))) { Fail "Run this script from the ISL-NOVA repository (backend\app\main.py not found)." }

# ---------------------------------------------------------------- prerequisites
Step "Checking prerequisites"
$pyExe = $null; $pyArgs = @()
if ($Python) {
  $parts = $Python.Split(" "); $pyExe = $parts[0]; if ($parts.Length -gt 1) { $pyArgs = $parts[1..($parts.Length - 1)] }
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  $has313 = $false
  try { & py -3.13 -c "import sys" *> $null; $has313 = ($LASTEXITCODE -eq 0) } catch { $has313 = $false }
  $pyExe = "py"; if ($has313) { $pyArgs = @("-3.13") } else { $pyArgs = @("-3") }
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
  $pyExe = "python"
} else {
  Fail "Python 3.11+ not found. Install Python 3.13 from https://www.python.org/downloads/windows/ (tick 'Add python.exe to PATH')."
}
$pyVer = & $pyExe @pyArgs -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ($LASTEXITCODE -ne 0) { Fail "Could not run Python ($pyExe $pyArgs)." }
$maj, $min = $pyVer.Split("."); if ([int]$maj -lt 3 -or ([int]$maj -eq 3 -and [int]$min -lt 11)) { Fail "Python $pyVer found; 3.11 or newer is required (3.13 recommended)." }
Ok "Python $pyVer ($pyExe $pyArgs)"

if (-not $SkipFrontend) {
  if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Fail "Node.js not found. Install Node.js 22 LTS from https://nodejs.org/ ." }
  $nodeMajor = [int]((& node -p "process.versions.node.split('.')[0]"))
  if ($nodeMajor -lt 20) { Fail "Node.js $nodeMajor found; 20 or newer is required (22 recommended)." }
  Ok "Node.js $(& node --version), npm $(& npm --version)"
}
if (Get-Command git -ErrorAction SilentlyContinue) { Ok "$(& git --version)" } else { Write-Host "    note: git not on PATH (only needed to pull updates)" }

# ---------------------------------------------------------------- python env
Step "Creating the Python virtual environment (.venv)"
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { Run $pyExe ($pyArgs + @("-m", "venv", ".venv")) "venv creation" } else { Ok ".venv already exists" }
Run $venvPy @("-m", "pip", "install", "--upgrade", "pip", "--quiet") "pip upgrade"
Step "Installing Python packages (backend\requirements-dev.txt)"
Run $venvPy @("-m", "pip", "install", "-r", "backend\requirements-dev.txt") "pip install"
Ok "Python packages installed"

# ---------------------------------------------------------------- frontend
if (-not $SkipFrontend) {
  Step "Installing and building the frontend"
  Push-Location frontend
  try {
    $installed = $false
    if (Test-Path package-lock.json) {
      & npm ci --no-audit --no-fund
      if ($LASTEXITCODE -eq 0) { $installed = $true }
      else { Write-Host "    package-lock.json is out of date; refreshing it with npm install" -ForegroundColor Yellow }
    }
    if (-not $installed) { & npm install --no-audit --no-fund }
    if ($LASTEXITCODE -ne 0) { Fail "npm install failed" }
    & npm run build
    if ($LASTEXITCODE -ne 0) { Fail "frontend build failed" }
  } finally { Pop-Location }
  Ok "frontend\dist built"
}

# ---------------------------------------------------------------- .env
Step "Configuring .env"
$envFile = Join-Path $Root ".env"
if (-not (Test-Path $envFile)) {
  $secret = & $venvPy -c "import secrets; print(secrets.token_urlsafe(48))"
  $adminPw = & $venvPy -c "import secrets; print(secrets.token_urlsafe(12))"
  $lines = Get-Content (Join-Path $Root ".env.example")
  $out = foreach ($l in $lines) {
    if ($l -match '^JWT_SECRET=') { "JWT_SECRET=$secret" }
    elseif ($l -match '^BOOTSTRAP_ADMIN_EMAIL=') { "BOOTSTRAP_ADMIN_EMAIL=$AdminEmail" }
    elseif ($l -match '^BOOTSTRAP_ADMIN_PASSWORD=') { "BOOTSTRAP_ADMIN_PASSWORD=$adminPw" }
    else { $l }
  }
  Set-Content -Path $envFile -Value $out -Encoding ascii
  Ok ".env created (git-ignored). Local admin: $AdminEmail, password in .env (BOOTSTRAP_ADMIN_PASSWORD); change it after first login"
} else {
  Ok ".env already exists; left unchanged"
}

# ---------------------------------------------------------------- load env helper
function Import-DotEnv($path) {
  foreach ($line in Get-Content $path) {
    if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
    $k, $v = $line.Split("=", 2); $k = $k.Trim()
    if ($k) { [Environment]::SetEnvironmentVariable($k, $v.Trim(), "Process") }
  }
}
Import-DotEnv $envFile
$env:PYTHONPATH = "$Root\backend;$Root\ml"

# ---------------------------------------------------------------- MediaPipe tasks (optional)
if ($WithMediaPipeTasks) {
  Step "Downloading MediaPipe task files (server-side video analysis)"
  $mp = Join-Path $Root "artifacts\mediapipe"; New-Item -ItemType Directory -Force -Path $mp | Out-Null
  $hand = Join-Path $mp "hand_landmarker.task"; $pose = Join-Path $mp "pose_landmarker_lite.task"
  if (-not (Test-Path $hand)) { Invoke-WebRequest -UseBasicParsing -Uri "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task" -OutFile $hand }
  if (-not (Test-Path $pose)) { Invoke-WebRequest -UseBasicParsing -Uri "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task" -OutFile $pose }
  $content = Get-Content $envFile
  $content = $content | ForEach-Object {
    if ($_ -match '^ISL_NOVA_HAND_MODEL=') { "ISL_NOVA_HAND_MODEL=$hand" } elseif ($_ -match '^ISL_NOVA_POSE_MODEL=') { "ISL_NOVA_POSE_MODEL=$pose" } else { $_ }
  }
  Set-Content -Path $envFile -Value $content -Encoding ascii
  Ok "MediaPipe task files in artifacts\mediapipe (paths written to .env)"
}

# ---------------------------------------------------------------- database
Step "Preparing the database"
# run from the repository root so relative paths in .env resolve the same way as in start_windows.ps1
Run $venvPy @("-m", "app.migrate") "database migration"
Ok "database ready ($env:DATABASE_URL)"

# ---------------------------------------------------------------- model
if (-not $SkipModel) {
  Step "Installing the trained model $ModelTag"
  $registry = $env:MODEL_REGISTRY_DIR; if (-not $registry) { $registry = "artifacts\models" }
  Run $venvPy @("scripts\fetch_model.py", "--tag", $ModelTag, "--registry", $registry, "--promote", "--keep-active") "model download/verification"
  Ok "model installed in $registry (activated only if no model was active)"
  & $venvPy scripts\fetch_references.py
  if ($LASTEXITCODE -eq 0) { Ok "sign references installed (Practice Coach, Text-to-Sign)" }
  else { Write-Host "    note: sign references could not be downloaded; Practice Coach will report them missing" -ForegroundColor Yellow }
} else {
  Write-Host "    skipped: recognition will show 'model unavailable' until a model is installed"
}

Write-Host "`nSetup complete. Start ISL NOVA with:" -ForegroundColor Green
Write-Host "    powershell -ExecutionPolicy Bypass -File scripts\start_windows.ps1"
