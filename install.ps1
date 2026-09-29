param([Parameter(Mandatory=$true)][Alias('Target')][string]$Workspace, [string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$installArgs = @((Join-Path $PSScriptRoot 'scripts/manage_install.py'), 'install', '--workspace', $Workspace)
& $Python @installArgs
exit $LASTEXITCODE
