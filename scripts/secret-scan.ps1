$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$patterns = @(
    'AKIA[0-9A-Z]{16}',
    'gh[pousr]_[A-Za-z0-9_]{30,}',
    '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----',
    '(?i)(api[_-]?key|client[_-]?secret|password)\s*[=:]\s*["''][^"'']{12,}'
)

$found = $false
foreach ($pattern in $patterns) {
    $matches = rg --line-number --with-filename --color never `
        -g '!*.pdf' `
        -g '!*.png' `
        -g '!*.jpg' `
        -g '!*.jpeg' `
        -g '!*.webp' `
        -g '!*.avif' `
        -g '!*.ico' `
        -g '!*.woff' `
        -g '!*.woff2' `
        -g '!*.sqlite3' `
        -g '!.local/**' `
        -g '!node_modules/**' `
        -g '!.venv/**' `
        -g '!.git/**' `
        --regexp $pattern . 2>$null
    if ($LASTEXITCODE -gt 1) {
        throw "Secret scan failed while evaluating a configured pattern."
    }
    if ($LASTEXITCODE -eq 0 -and $matches) {
        $found = $true
        $matches | ForEach-Object {
            $parts = $_ -split ':', 3
            Write-Output "Potential secret pattern: $($parts[0]):$($parts[1]) [value redacted]"
        }
    }
}

if ($found) {
    throw 'Potential credential material was detected; review masked paths.'
}
Write-Output 'Secret scan passed without credential or private-key patterns.'
