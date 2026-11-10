<#
.SYNOPSIS
  Run the ISL NOVA test suites on Windows (after scripts\setup_windows.ps1).

.DESCRIPTION
  Run from the repository root:
      powershell -ExecutionPolicy Bypass -File scripts\test_windows.ps1            # lint, Python, TS, unit
      powershell -ExecutionPolicy Bypass -File scripts\test_windows.ps1 -E2E       # + browser end-to-end
      powershell -ExecutionPolicy Bypass -File scripts\test_windows.ps1 -E2E -WithModel   # + tests with the trained model

  Exits non-zero if any suite fails, and prints a summary table.
#>
[CmdletBinding()]
param(
  [switch]$E2E,
  [switch]$WithModel,
  [string]$ModelTag = "model-lstm-20261110T111537Z-s7"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { Write-Host "ERROR  No .venv found. Run scripts\setup_windows.ps1 first." -ForegroundColor Red; exit 1 }
$env:PYTHONPATH = "$Root\backend;$Root\ml"
$env:PYTHON = $venvPy   # used by the E2E harness to start the server
$results = @()

function Suite($name, [scriptblock]$body) {
  Write-Host "`n==> $name" -ForegroundColor Cyan
  $t0 = Get-Date
  & $body
  $ok = ($LASTEXITCODE -eq 0)
  $script:results += [pscustomobject]@{ Suite = $name; Result = $(if ($ok) { "PASS" } else { "FAIL" }); Seconds = [int]((Get-Date) - $t0).TotalSeconds }
}

Suite "Lint (ruff)" { & $venvPy -m ruff check backend ml dataset/scripts scripts }
Suite "Backend + ML tests (pytest)" { & $venvPy -m pytest -q }
Push-Location frontend
try {
  Suite "Frontend type check" { & npm run typecheck }
  Suite "Frontend unit tests" { & npm test }
  if ($E2E) {
    Suite "Playwright Chromium" { & npx playwright install chromium }
    Suite "Frontend build" { & npm run build }
    if ($WithModel) { $env:E2E_MODEL_TAG = $ModelTag } else { Remove-Item Env:E2E_MODEL_TAG -ErrorAction SilentlyContinue }
    Suite "End-to-end (Chromium)" { & npm run e2e }
  }
} finally { Pop-Location }

Write-Host ""
$results | Format-Table -AutoSize
if ($results | Where-Object { $_.Result -eq "FAIL" }) { Write-Host "Some suites failed." -ForegroundColor Red; exit 1 }
Write-Host "All suites passed." -ForegroundColor Green
