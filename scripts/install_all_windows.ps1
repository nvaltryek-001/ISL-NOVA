<#
.SYNOPSIS
  ISL NOVA: complete local installation on Windows in one command.

.DESCRIPTION
  Run from the repository root:
      powershell -ExecutionPolicy Bypass -File scripts\install_all_windows.ps1

  Does everything, in order, and prints a summary at the end:
    1. checks Python 3.11+, Node.js 20+, Git (and tells you where to get them)
    2. creates .venv and installs all Python packages
    3. installs and builds the frontend
    4. creates .env (random secret, local admin account)
    5. prepares the SQLite database (200 vocabulary slots)
    6. installs the trained 200-class LSTM (SHA-256 verified)
    7. downloads the MediaPipe task files (server-side Video Analysis)
    8. downloads the processed INCLUDE dataset (3,370 sequences, 176 MB, no sign-in)
    9. checks recognition end to end (24 held-out sequences through a local server)
   10. optionally trains a model (-Train) and/or starts the app (-Start)

  Safe to run again: finished steps are skipped or refreshed.

.PARAMETER Train
  Also train a model on the downloaded dataset: lstm, gru, pooled-logreg, dtw-1nn or all.
.PARAMETER Start
  Start the app at the end and open the browser.
.PARAMETER SkipDataset
  Do not download the 176 MB dataset (only needed for training).
.PARAMETER Port
  Port used for the check and for -Start (default 8000).
.PARAMETER Python
  Python launcher to use, e.g. "py -3.13" or "python" (default: detected).
#>
[CmdletBinding()]
param(
  [ValidateSet("", "lstm", "lstm-fps", "gru", "gru-fps", "bilstm-attn", "transformer", "tcn", "pooled-logreg", "dtw-1nn", "all")][string]$Train = "",
  [switch]$Start,
  [switch]$SkipDataset,
  [int]$Port = 8000,
  [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$t0 = Get-Date
$done = @()

function Banner($n, $msg) { Write-Host "`n[$n/10] $msg" -ForegroundColor Magenta }
function Fail($msg) { Write-Host "`nERROR  $msg" -ForegroundColor Red; exit 1 }

Write-Host "ISL NOVA complete installation" -ForegroundColor Cyan
Write-Host "Repository: $Root"

# ---------------------------------------------------------------- 1-7: base setup
Banner "1-7" "Prerequisites, Python packages, frontend, .env, database, trained model, MediaPipe files"
$setupArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $PSScriptRoot "setup_windows.ps1"), "-WithMediaPipeTasks")
if ($Python) { $setupArgs += @("-Python", $Python) }
& powershell @setupArgs
if ($LASTEXITCODE -ne 0) {
  Fail ("base setup failed (see the message above).`n" +
        "  Python 3.13: https://www.python.org/downloads/windows/  (tick 'Add python.exe to PATH')`n" +
        "  Node.js 22 LTS: https://nodejs.org/   Git: https://git-scm.com/download/win`n" +
        "  Then close and reopen PowerShell and run this script again.")
}
$done += "Python environment, packages, frontend build, .env, database, trained model, MediaPipe files"
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"

# ---------------------------------------------------------------- 8: dataset
if (-not $SkipDataset) {
  Banner 8 "Processed INCLUDE dataset (176 MB, CC BY 4.0)"
  & $venvPy scripts\train_local.py --download-only
  if ($LASTEXITCODE -ne 0) { Fail "dataset download failed; check your internet connection and run again (or use -SkipDataset)" }
  $done += "INCLUDE landmark dataset in data\include-landmarks-v1"
} else { Banner 8 "Dataset skipped (-SkipDataset)" }

# ---------------------------------------------------------------- 9: end-to-end check
Banner 9 "End-to-end check: start a temporary server and recognise 24 held-out sequences"
$busy = $false
try { $c = New-Object System.Net.Sockets.TcpClient; $c.Connect("127.0.0.1", $Port); $busy = $c.Connected; $c.Close() } catch { $busy = $false }
if ($busy) {
  Write-Host "    port $Port is in use (ISL NOVA already running?). Checking against the running server instead."
  & $venvPy scripts\check_predictions.py --base "http://127.0.0.1:$Port"
  $checkOk = ($LASTEXITCODE -eq 0)
} else {
  # run in-process: a child PowerShell whose output is piped would wait for the background server to exit
  & (Join-Path $PSScriptRoot "start_windows.ps1") -Background -NoBrowser -Port $Port
  if ($LASTEXITCODE -ne 0) { Fail "the server did not start; see storage\server.log.err" }
  Set-Location $Root
  & $venvPy scripts\check_predictions.py --base "http://127.0.0.1:$Port"
  $checkOk = ($LASTEXITCODE -eq 0)
  Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*uvicorn*--port $Port*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
if (-not $checkOk) { Fail "recognition check failed (fewer than 18 of 24 held-out sequences correct)" }
$done += "Recognition check passed (held-out INCLUDE sequences through the local API)"

# ---------------------------------------------------------------- 10: optional training / start
if ($Train) {
  Banner 10 "Training: $Train"
  & $venvPy scripts\train_local.py --model $Train
  if ($LASTEXITCODE -ne 0) { Fail "training failed" }
  $done += "Trained $Train (registered, not promoted; promote it in AI Laboratory -> Registry)"
} else { Banner 10 "Training skipped (add -Train lstm, or -Train all)" }

$mins = [math]::Round(((Get-Date) - $t0).TotalMinutes, 1)
Write-Host "`n================ ISL NOVA is installed ($mins min) ================" -ForegroundColor Green
foreach ($d in $done) { Write-Host "  OK  $d" -ForegroundColor Green }
Write-Host ""
Write-Host "  Admin login : admin email printed above; password = BOOTSTRAP_ADMIN_PASSWORD in .env"
Write-Host "  Start       : powershell -ExecutionPolicy Bypass -File scripts\start_windows.ps1"
Write-Host "  Tests       : powershell -ExecutionPolicy Bypass -File scripts\test_windows.ps1 -E2E -WithModel"
Write-Host "  Train       : powershell -ExecutionPolicy Bypass -File scripts\train_windows.ps1 -Model all"
Write-Host "  Open        : http://127.0.0.1:$Port  (Live Recognition needs camera permission)"

if ($Start) {
  & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "start_windows.ps1") -Port $Port
}
