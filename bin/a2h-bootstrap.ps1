param([Parameter(Mandatory=$true)][string]$Source, [string]$Project = (Get-Location).Path)
$ErrorActionPreference = 'Stop'
$Runtime = Join-Path (Get-Location).Path '.hmigbot-ios/plugin'
if (-not (Test-Path -LiteralPath (Join-Path $Runtime 'scripts/a2h_ios.py'))) {
  $Runtime = Split-Path -Parent $PSScriptRoot
}
$NativePython = if ($env:PYTHON) { $env:PYTHON } else { 'python' }
& $NativePython -X utf8 (Join-Path $Runtime 'scripts/a2h_ios.py') init --source $Source --project $Project
exit $LASTEXITCODE
