param(
    [Parameter(Mandatory = $true)][string]$Backup,
    [Parameter(Mandatory = $true)][ValidateSet("RESTORE")][string]$ConfirmRestore
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backupRoot = (Resolve-Path (Join-Path $projectRoot "backups")).Path
$resolvedBackup = (Resolve-Path -LiteralPath $Backup).Path
if (-not $resolvedBackup.StartsWith($backupRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Restore source must be inside $backupRoot"
}
if ([System.IO.Path]::GetExtension($resolvedBackup) -ne ".dump") {
    throw "Restore source must be a .dump file."
}

$fileName = Split-Path -Leaf $resolvedBackup
Push-Location $projectRoot
try {
    docker compose exec -T postgres pg_restore --list "/backups/$fileName" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Backup verification failed before restore." }
    docker compose stop api worker
    docker compose exec -T postgres pg_restore --username shadowgrid --dbname shadowgrid --clean --if-exists --no-owner "/backups/$fileName"
    if ($LASTEXITCODE -ne 0) { throw "Restore failed with exit code $LASTEXITCODE" }
    docker compose start api worker
}
finally {
    Pop-Location
}

Write-Output "Restore completed from $resolvedBackup"
