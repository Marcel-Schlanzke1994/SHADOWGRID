param(
    [Parameter(Mandatory = $true)][string]$ProjectRoot,
    [Parameter(Mandatory = $true)][string]$Backup
)

$ErrorActionPreference = "Stop"
$resolvedProject = (Resolve-Path -LiteralPath $ProjectRoot).Path
$backupRoot = (Resolve-Path -LiteralPath (Join-Path $resolvedProject "backups")).Path
$resolvedBackup = (Resolve-Path -LiteralPath $Backup).Path
$allowedPrefix = $backupRoot.TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
) + [System.IO.Path]::DirectorySeparatorChar
if (-not $resolvedBackup.StartsWith(
    $allowedPrefix,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "Restore source must be inside $backupRoot"
}
$extension = [System.IO.Path]::GetExtension($resolvedBackup)
if ($extension -notin @(".dump", ".sqlite3")) {
    throw "Restore source must be a .dump or .sqlite3 file."
}

Write-Output $resolvedBackup
