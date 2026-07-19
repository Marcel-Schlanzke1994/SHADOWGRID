param([string]$Label = "manual")

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backupRoot = Join-Path $projectRoot "backups"
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
$safeLabel = $Label -replace "[^a-zA-Z0-9_-]", "-"
$fileName = "shadowgrid-$timestamp-$safeLabel.dump"

Push-Location $projectRoot
try {
    docker compose exec -T postgres pg_dump --username shadowgrid --dbname shadowgrid --format custom --file "/backups/$fileName"
    if ($LASTEXITCODE -ne 0) { throw "pg_dump failed with exit code $LASTEXITCODE" }
    docker compose exec -T postgres pg_restore --list "/backups/$fileName" | Select-Object -First 5
    if ($LASTEXITCODE -ne 0) { throw "Backup verification failed." }
}
finally {
    Pop-Location
}

Write-Output "Verified backup: $backupRoot\$fileName"
