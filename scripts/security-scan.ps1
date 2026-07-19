$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$patterns = @(
    'AKIA[0-9A-Z]{16}',
    'gh[pousr]_[A-Za-z0-9_]{30,}',
    '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----',
    '(?i)(api[_-]?key|client[_-]?secret|password)\s*[=:]\s*["''][^"'']{12,}'
)

$trackedFiles = rg --files -g '!*.pdf' -g '!.local/**' -g '!node_modules/**' -g '!.venv/**' -g '!.git/**'
$found = $false
foreach ($pattern in $patterns) {
    $matches = $trackedFiles | rg --line-number --with-filename --color never --regexp $pattern 2>$null
    if ($LASTEXITCODE -eq 0 -and $matches) {
        $found = $true
        $matches | ForEach-Object {
            $parts = $_ -split ':', 3
            Write-Output "Potential secret pattern: $($parts[0]):$($parts[1]) [value redacted]"
        }
    }
}

& "$projectRoot\.venv\Scripts\python.exe" -m bandit -q -r apps/api/shadowgrid apps/worker
if ($LASTEXITCODE -ne 0) { throw 'Bandit found a security issue.' }
& "$projectRoot\.venv\Scripts\python.exe" -m pip_audit -r apps/api/requirements.txt --progress-spinner=off
if ($LASTEXITCODE -ne 0) { throw 'Python dependency audit failed.' }
pnpm audit --audit-level high
if ($LASTEXITCODE -ne 0) { throw 'JavaScript dependency audit failed.' }

if ($found) { throw 'Potential credential material was detected; review masked paths.' }
Write-Output 'Security scan passed without credential patterns or high-severity audit findings.'
