<#
.SYNOPSIS
  Change a user's password from the terminal (loads .env so it edits the same database as the app).

      powershell -ExecutionPolicy Bypass -File scripts\password_windows.ps1                 # lists users
      powershell -ExecutionPolicy Bypass -File scripts\password_windows.ps1 -Email you@x.org  # asks for the new password twice

  The new password must be at least 10 characters. All existing sign-ins of that user are signed out.
  If .env still holds the first-run BOOTSTRAP_ADMIN_PASSWORD, you can delete that line afterwards.
#>
param([string]$Email = "")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$envFile = Join-Path $Root ".env"
if (-not (Test-Path $envFile)) { Write-Host "ERROR  no .env found; run scripts\setup_windows.ps1 first" -ForegroundColor Red; exit 1 }
foreach ($line in Get-Content $envFile) {
  if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
  $k, $v = $line.Split("=", 2); $k = $k.Trim()
  if ($k) { [Environment]::SetEnvironmentVariable($k, $v.Trim(), "Process") }
}
$env:PYTHONPATH = "$Root\backend;$Root\ml"
$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not $Email) { & $py -m app.manage list-users; Write-Host "`nThen: scripts\password_windows.ps1 -Email <email>"; exit $LASTEXITCODE }
& $py -m app.manage set-password --email $Email
exit $LASTEXITCODE
