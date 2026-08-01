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
    powershell -ExecutionPolicy Bypass -File scripts/project.ps1 setup
    if ($LASTEXITCODE -ne 0) {
        throw "Local setup failed with exit code $LASTEXITCODE."
    }
    if ($resolvedMode -eq 'Compose') {
        docker compose build api worker web
        if ($LASTEXITCODE -ne 0) {
            throw "Compose build failed with exit code $LASTEXITCODE."
        }
    }
}
finally {
    Pop-Location
}

Write-Output "SHADOWGRID local setup completed in $resolvedMode mode."
Write-Output 'Local credentials remain in .local\demo-credentials.txt and are not printed.'
