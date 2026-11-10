<#
.SYNOPSIS
  Start ISL NOVA locally on Windows (after scripts\setup_windows.ps1).

.DESCRIPTION
  Run from the repository root:
      powershell -ExecutionPolicy Bypass -File scripts\start_windows.ps1

  Loads .env, starts the API + web app on http://127.0.0.1:<Port>, waits for
  /api/v1/health, prints the model status and opens the browser. Press Ctrl+C
  to stop. The camera works on http://localhost / 127.0.0.1 (secure context).

.PARAMETER Port
  Port for the server (default 8000).
.PARAMETER Dev
  Also run the frontend in watch mode (rebuilds frontend\dist on change) in a
  second window.
.PARAMETER NoBrowser
  Do not open the browser.
.PARAMETER Background
  Start the server in the background, check health, print its process id and
  return (used by CI; stop it with Stop-Process -Id <pid>).
#>
[CmdletBinding()]
param(
  [int]$Port = 8000,
  [switch]$Dev,
  [switch]$NoBrowser,
  [switch]$Background
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Fail($msg) { Write-Host "ERROR  $msg" -ForegroundColor Red; exit 1 }

$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { Fail "No .venv found. Run scripts\setup_windows.ps1 first." }
if (-not (Test-Path (Join-Path $Root "frontend\dist\index.html"))) { Fail "frontend\dist is missing. Run scripts\setup_windows.ps1 (or: cd frontend; npm run build)." }

$envFile = Join-Path $Root ".env"
if (Test-Path $envFile) {
  foreach ($line in Get-Content $envFile) {
    if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
    $k, $v = $line.Split("=", 2); $k = $k.Trim()
    if ($k) { [Environment]::SetEnvironmentVariable($k, $v.Trim(), "Process") }
  }
} else {
  Write-Host "note: no .env found; using development defaults (ephemeral JWT secret, no admin account)" -ForegroundColor Yellow
}
$env:PYTHONPATH = "$Root\backend;$Root\ml"
$base = "http://127.0.0.1:$Port"
$origins = @("http://127.0.0.1:$Port", "http://localhost:$Port")
if ($env:CORS_ORIGINS) { $origins += $env:CORS_ORIGINS.Split(",") }
$env:CORS_ORIGINS = ($origins | Select-Object -Unique) -join ","

# refuse to start if something already listens on the port (e.g. an earlier ISL NOVA window)
$busy = $false
try { $c = New-Object System.Net.Sockets.TcpClient; $c.Connect("127.0.0.1", $Port); $busy = $c.Connected; $c.Close() } catch { $busy = $false }
if ($busy) {
  Fail ("port $Port is already in use. Is ISL NOVA already running in another window? Open $base, " +
        "stop the other server with Ctrl+C, or start on another port: scripts\start_windows.ps1 -Port 8080")
}

# database migrations are idempotent
& $venvPy -m app.migrate | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "database migration failed; check DATABASE_URL in .env" }

if ($Dev) {
  Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", "Set-Location '$Root\frontend'; npm run dev" | Out-Null
  Write-Host "frontend watch mode started in a second window"
}

$uvArgs = @("-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "$Port")

function Wait-Healthy {
  for ($i = 0; $i -lt 90; $i++) {
    try {
      $h = Invoke-RestMethod -Uri "$base/api/v1/health" -TimeoutSec 2
      if ($h.status -eq "ok") { return $h }
    } catch { Start-Sleep -Seconds 1 }
  }
  return $null
}

function Show-Status($h) {
  $m = Invoke-RestMethod -Uri "$base/api/v1/model/info"
  Write-Host "`nISL NOVA is running at $base" -ForegroundColor Green
  Write-Host ("  database : {0}, migrations pending: {1}" -f $h.database, $h.migrations.pending.Count)
  if ($m.available) {
    Write-Host ("  model    : {0} ({1}, {2} classes, synthetic={3})" -f $m.model_id, $m.kind, $m.n_classes, $m.synthetic)
  } else {
    Write-Host "  model    : not installed (run scripts\setup_windows.ps1 without -SkipModel)" -ForegroundColor Yellow
  }
  Write-Host "  API docs : $base/api/docs"
}

if ($Background) {
  $log = Join-Path $Root "storage\server.log"
  New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
  $p = Start-Process -FilePath $venvPy -ArgumentList $uvArgs -RedirectStandardOutput $log -RedirectStandardError "$log.err" -PassThru -WindowStyle Hidden
  $h = Wait-Healthy
  if (-not $h) { Get-Content "$log.err" -Tail 30; Fail "server did not become healthy on $base" }
  Show-Status $h
  Write-Host "  pid      : $($p.Id)  (stop with: Stop-Process -Id $($p.Id))"
  exit 0
}

$p = Start-Process -FilePath $venvPy -ArgumentList $uvArgs -NoNewWindow -PassThru
try {
  $h = Wait-Healthy
  if (-not $h) { Fail "server did not become healthy on $base" }
  Show-Status $h
  if (-not $NoBrowser) { Start-Process $base | Out-Null }
  Write-Host "`nPress Ctrl+C to stop." -ForegroundColor Cyan
  Wait-Process -Id $p.Id
} finally {
  if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
}
