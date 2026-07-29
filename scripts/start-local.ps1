param(
    [ValidateSet('Auto', 'Compose', 'SQLite')]
    [string]$Mode = 'Auto',
    [switch]$SkipSetup
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-common.ps1')
$projectRoot = Get-ShadowgridProjectRoot
$resolvedMode = Resolve-ShadowgridMode -Mode $Mode

if (-not $SkipSetup) {
    & (Join-Path $PSScriptRoot 'setup-local.ps1') -Mode $resolvedMode
}

Push-Location $projectRoot
try {
    if ($resolvedMode -eq 'Compose') {
        docker compose up --build -d postgres redis mailpit minio api worker web prometheus
        if ($LASTEXITCODE -ne 0) { throw 'Compose startup failed.' }
        docker compose exec -T api python -m shadowgrid.predeploy
        if ($LASTEXITCODE -ne 0) { throw 'Compose predeploy failed.' }
        docker compose exec -T api python -m shadowgrid.seed
        if ($LASTEXITCODE -ne 0) { throw 'Compose demo seed failed.' }
    }
    else {
        $python = Join-Path $projectRoot '.venv\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $python)) {
            throw 'The local Python environment is missing. Run setup-local.ps1 first.'
        }
        $pnpmCommand = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
        if ($null -eq $pnpmCommand) {
            throw 'pnpm.cmd is required for the Windows local web process.'
        }
        Start-ShadowgridManagedProcess `
            -Name 'api' `
            -FilePath $python `
            -ArgumentList @('-m', 'uvicorn', 'shadowgrid.main:app', '--host', '127.0.0.1', '--port', '8000') `
            -WorkingDirectory (Join-Path $projectRoot 'apps\api') `
            -Marker 'uvicorn'
        Start-ShadowgridManagedProcess `
            -Name 'worker' `
            -FilePath $python `
            -ArgumentList @('-m', 'worker.local_worker') `
            -WorkingDirectory (Join-Path $projectRoot 'apps') `
            -Marker 'local_worker'
        Start-ShadowgridManagedProcess `
            -Name 'web' `
            -FilePath $pnpmCommand.Source `
            -ArgumentList @('--filter', '@shadowgrid/web', 'dev') `
            -WorkingDirectory $projectRoot `
            -Marker '@shadowgrid/web'
    }

    & (Join-Path $PSScriptRoot 'verify-local.ps1') -Mode $resolvedMode
}
finally {
    Pop-Location
}

$webPort = if ($resolvedMode -eq 'Compose') {
    Get-ShadowgridEnvValue -Name 'FRONTEND_PORT' -Default '3000'
} else {
    '5173'
}
Write-Output "SHADOWGRID is ready in $resolvedMode mode."
Write-Output "Web: http://localhost:$webPort"
Write-Output 'API: http://localhost:8000/api/v1'
if ($resolvedMode -eq 'Compose') {
    Write-Output 'Mailpit: http://localhost:8025'
    Write-Output 'Prometheus: http://localhost:9090'
}
Write-Output 'Demo credentials: .local\demo-credentials.txt (contents intentionally not printed).'
