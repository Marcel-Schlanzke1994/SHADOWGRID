param(
    [ValidateSet('Auto', 'Compose', 'SQLite')]
    [string]$Mode = 'Auto',
    [Parameter(Mandatory)]
    [ValidateSet('RESET')]
    [string]$ConfirmReset,
    [switch]$Start
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-common.ps1')
$projectRoot = Get-ShadowgridProjectRoot
$resolvedMode = Resolve-ShadowgridMode -Mode $Mode

& (Join-Path $PSScriptRoot 'stop-local.ps1') -Mode $resolvedMode
Push-Location $projectRoot
try {
    if ($resolvedMode -eq 'Compose') {
        docker compose down --volumes --remove-orphans
        if ($LASTEXITCODE -ne 0) { throw 'Compose reset failed.' }
    }
    else {
        $localRoot = (Resolve-Path -LiteralPath (Join-Path $projectRoot '.local')).Path
        $databasePath = Join-Path $localRoot 'shadowgrid.db'
        if (-not $databasePath.StartsWith($localRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw 'Resolved SQLite path escaped the local state directory.'
        }
        if (Test-Path -LiteralPath $databasePath) {
            Remove-Item -LiteralPath $databasePath -Force
        }
    }
}
finally {
    Pop-Location
}

& (Join-Path $PSScriptRoot 'setup-local.ps1') -Mode $resolvedMode
if ($Start) {
    & (Join-Path $PSScriptRoot 'start-local.ps1') -Mode $resolvedMode -SkipSetup
}
Write-Output "SHADOWGRID $resolvedMode local state reset and reseeded."
