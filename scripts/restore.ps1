param(
    [Parameter(Mandatory = $true)][string]$Backup,
    [Parameter(Mandatory = $true)][ValidateSet("RESTORE")][string]$ConfirmRestore
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$resolvedBackup = & (Join-Path $PSScriptRoot "resolve-backup-path.ps1") `
    -ProjectRoot $projectRoot `
    -Backup $Backup
$extension = [System.IO.Path]::GetExtension($resolvedBackup)
if ($extension -eq ".sqlite3") {
    Push-Location $projectRoot
    try {
        node scripts/run-python.mjs --cwd apps/api -m shadowgrid.local_backups restore `
            --backup $resolvedBackup `
            --confirm $ConfirmRestore
        if ($LASTEXITCODE -ne 0) { throw "SQLite restore failed with exit code $LASTEXITCODE" }
    }
    finally {
        Pop-Location
    }
    return
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required to restore a PostgreSQL custom dump."
}

$fileName = Split-Path -Leaf $resolvedBackup
$servicesMayBeStopped = $false
Push-Location $projectRoot
try {
    docker compose exec -T postgres pg_restore --list "/backups/$fileName" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Backup verification failed before restore." }
    $servicesMayBeStopped = $true
    docker compose stop api worker
    if ($LASTEXITCODE -ne 0) { throw "Stopping API and worker failed." }
    docker compose exec -T postgres pg_restore --username shadowgrid --dbname shadowgrid --clean --if-exists --no-owner "/backups/$fileName"
    if ($LASTEXITCODE -ne 0) { throw "Restore failed with exit code $LASTEXITCODE" }
}
finally {
    if ($servicesMayBeStopped) {
        docker compose start api worker
        if ($LASTEXITCODE -ne 0) { throw "Restarting API and worker failed." }
    }
    Pop-Location
}

Write-Output "Restore completed from $resolvedBackup"
