param(
    [ValidateSet('Auto', 'Compose', 'SQLite')]
    [string]$Mode = 'Auto'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-common.ps1')
$projectRoot = Get-ShadowgridProjectRoot
$resolvedMode = Resolve-ShadowgridMode -Mode $Mode

if ($resolvedMode -eq 'Compose') {
    $running = @(docker compose ps --status running --services)
    foreach ($service in @('postgres', 'redis', 'api', 'worker', 'web')) {
        if ($service -notin $running) {
            throw "Required Compose service '$service' is not running."
        }
    }
}
else {
    foreach ($name in @('api', 'worker', 'web')) {
        if (-not (Test-ShadowgridManagedProcess -Name $name)) {
            throw "Required SQLite-mode process '$name' is not running."
        }
    }
}

Wait-ShadowgridHttp -Uri 'http://127.0.0.1:8000/api/v1/health'
Wait-ShadowgridHttp -Uri 'http://127.0.0.1:8000/api/v1/ready'
$webPort = if ($resolvedMode -eq 'Compose') {
    Get-ShadowgridEnvValue -Name 'FRONTEND_PORT' -Default '3000'
} else {
    '5173'
}
Wait-ShadowgridHttp -Uri "http://127.0.0.1:$webPort/healthz"

Push-Location $projectRoot
try {
    pnpm data:verify
    if ($LASTEXITCODE -ne 0) { throw 'Release data invariants failed.' }
}
finally {
    Pop-Location
}

Write-Output "SHADOWGRID $resolvedMode health, readiness, worker and data checks passed."
