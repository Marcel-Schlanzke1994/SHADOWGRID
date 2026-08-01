param(
    [ValidateSet('Auto', 'Compose', 'SQLite')]
    [string]$Mode = 'Auto'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-common.ps1')
$projectRoot = Get-ShadowgridProjectRoot
$resolvedMode = Resolve-ShadowgridMode -Mode $Mode

Push-Location $projectRoot
try {
    if ($resolvedMode -eq 'Compose') {
        docker compose down
        if ($LASTEXITCODE -ne 0) { throw 'Compose shutdown failed.' }
    }
    else {
        Stop-ShadowgridManagedProcess -Name 'web'
        Stop-ShadowgridManagedProcess -Name 'worker'
        Stop-ShadowgridManagedProcess -Name 'api'
    }
}
finally {
    Pop-Location
}

Write-Output "SHADOWGRID $resolvedMode services stopped."
