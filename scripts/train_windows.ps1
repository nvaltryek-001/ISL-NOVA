<#
.SYNOPSIS
  Download the processed INCLUDE landmarks and train a model locally on Windows.

.DESCRIPTION
  Run from the repository root (after scripts\setup_windows.ps1):
      powershell -ExecutionPolicy Bypass -File scripts\train_windows.ps1                 # LSTM, ~10-20 min
      powershell -ExecutionPolicy Bypass -File scripts\train_windows.ps1 -Model all      # all four models
      powershell -ExecutionPolicy Bypass -File scripts\train_windows.ps1 -Model pooled-logreg   # ~1 min
      powershell -ExecutionPolicy Bypass -File scripts\train_windows.ps1 -Promote        # make it active

  The 176 MB landmark dataset is downloaded from the GitHub release
  dataset-include-landmarks-v1 (no sign-in, SHA-256 verified) into
  data\include-landmarks-v1. Use -Data <folder> for an existing copy.
#>
[CmdletBinding()]
param(
  [ValidateSet("lstm", "gru", "pooled-logreg", "dtw-1nn", "all")][string]$Model = "lstm",
  [string]$Data = "",
  [int]$Epochs = 0,
  [switch]$Promote
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { Write-Host "ERROR  No .venv found. Run scripts\setup_windows.ps1 first." -ForegroundColor Red; exit 1 }

$argv = @("scripts\train_local.py", "--model", $Model)
if ($Data) { $argv += @("--data", $Data) }
if ($Epochs -gt 0) { $argv += @("--epochs", "$Epochs") }
if ($Promote) { $argv += "--promote" }
& $venvPy @argv
exit $LASTEXITCODE
