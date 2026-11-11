<#
.SYNOPSIS
  ISL NOVA: run every remaining local step in one go, with a log you can share.

.DESCRIPTION
  Run from the repository root (stop the running app first with Ctrl+C):
      powershell -ExecutionPolicy Bypass -File scripts\complete_windows.ps1

  Steps (each one is resumable; rerun the same command after any interruption):
    1. update the code (git pull) and the install (packages, frontend build, model)
    2. full test suite: lint, pytest, type check, unit tests, browser E2E with the trained model
    3. full INCLUDE dataset: 56.8 GB download (MD5-verified, resumes) + landmark extraction
       with face points + merge into data\include\landmarks-face-v1
    4. train the face models, promote the best by validation score, fit the unknown-sign detector
    5. summary; then optionally start the app (-Start)

  Everything printed is also written to logs\complete-<date-time>.log.

.PARAMETER Workers       Parallel extraction processes (default 4).
.PARAMETER Model         What train_local.py trains (default all-face; e.g. bilstm-attn-face, all).
.PARAMETER SkipTests     Skip step 2.
.PARAMETER SkipDataset   Skip step 3 (and 4 unless the face dataset already exists).
.PARAMETER SkipTraining  Skip step 4.
.PARAMETER Start         Start the app at the end.
.PARAMETER KeepZips      Keep the 56.8 GB of video zips (default: each zip is deleted right after its
                         landmarks are extracted, so the run needs only about 15 GB free).
#>
[CmdletBinding()]
param(
  [int]$Workers = 4,
  [string]$Model = "all-face",
  [switch]$SkipTests,
  [switch]$SkipDataset,
  [switch]$SkipTraining,
  [switch]$Start,
  [switch]$KeepZips
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
New-Item -ItemType Directory -Force -Path (Join-Path $Root "logs") | Out-Null
$log = Join-Path $Root ("logs\complete-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
Start-Transcript -Path $log | Out-Null
$t0 = Get-Date
$py = Join-Path $Root ".venv\Scripts\python.exe"
$face = Join-Path $Root "data\include\landmarks-face-v1"
$status = [ordered]@{}

function Step($n, $msg) { Write-Host "`n================ [$n/5] $msg ================" -ForegroundColor Magenta }
function Run($name, [scriptblock]$body) {
  $s = Get-Date
  & $body | Out-Host   # show (and log) everything the step prints; only the result goes back to the caller
  $ok = ($LASTEXITCODE -eq 0)
  $script:status[$name] = "{0} ({1:N0} min)" -f $(if ($ok) { "OK" } else { "FAILED" }), ((Get-Date) - $s).TotalMinutes
  if (-not $ok) { Write-Host "    $name failed (see above). Continuing with the next step." -ForegroundColor Red }
  return $ok
}

try {
  Step 1 "Update code and install"
  Run "git pull" { git pull --ff-only } | Out-Null
  Run "install" { powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_all_windows.ps1 -SkipDataset } | Out-Null

  if (-not $SkipTests) {
    Step 2 "Full test suite (about 10-15 min)"
    Run "tests" { powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test_windows.ps1 -E2E -WithModel } | Out-Null
  } else { $status["tests"] = "skipped" }

  if (-not $SkipDataset) {
    Step 3 "Full INCLUDE dataset: download, extract, merge (hours; resumable)"
    $zipArg = @(); if (-not $KeepZips) { $zipArg = @("--delete-zips") }
    Run "dataset" { & $py scripts\include_local.py --workers $Workers @zipArg } | Out-Null
  } else { $status["dataset"] = "skipped" }

  if (-not $SkipTraining -and (Test-Path (Join-Path $face "manifest.json"))) {
    Step 4 "Train $Model, promote the best, fit the unknown-sign detector"
    Run "training" { & $py scripts\train_local.py --data $face --model $Model --promote } | Out-Null
  } elseif ($SkipTraining) { $status["training"] = "skipped" }
  else { $status["training"] = "not run: no face dataset yet (finish step 3)" }

  Step 5 "Summary"
  & $py -c "import json,pathlib; r=pathlib.Path('artifacts/models/registry.json'); d=json.loads(r.read_text()) if r.exists() else {}; a=d.get('active'); print('active model:', a); m=pathlib.Path('artifacts/models')/str(a)/'metrics.json'; t=json.loads(m.read_text())['test'] if m.exists() else {}; print('test top-1 %.1f %%, top-5 %.1f %%, macro-F1 %.1f %%' % (100*t['top1'],100*t['top5'],100*t['macro_f1'])) if t else None"
  $status.GetEnumerator() | ForEach-Object { "{0,-10} {1}" -f $_.Key, $_.Value } | Write-Host
  Write-Host ("total {0:N0} min. Log: {1}" -f ((Get-Date) - $t0).TotalMinutes, $log) -ForegroundColor Green
} finally {
  Stop-Transcript | Out-Null
}

if ($Start) { powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_windows.ps1 }
