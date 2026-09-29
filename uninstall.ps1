param([Parameter(Mandatory=$true)][string]$Workspace, [string]$Python = 'python')
$ErrorActionPreference = 'Stop'
& $Python (Join-Path $PSScriptRoot 'scripts/manage_install.py') uninstall --workspace $Workspace
exit $LASTEXITCODE
