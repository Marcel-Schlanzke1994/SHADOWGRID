$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

& "$PSScriptRoot\secret-scan.ps1"
if (-not $?) { throw 'Secret scan failed.' }
$global:LASTEXITCODE = 0

& "$projectRoot\.venv\Scripts\python.exe" -m bandit -q -r apps/api/shadowgrid apps/worker
if ($LASTEXITCODE -ne 0) { throw 'Bandit found a security issue.' }
& "$projectRoot\.venv\Scripts\python.exe" -m pip_audit -r apps/api/requirements.txt --progress-spinner=off
if ($LASTEXITCODE -ne 0) { throw 'Python dependency audit failed.' }
# The application uses React Router in client-only library mode. It does not install
# React Router's framework/RSC packages or expose server actions, so GHSA-qwww-vcr4-c8h2
# is not reachable. The reviewed exception is configured in pnpm-workspace.yaml. React
# Router 7.18.1 still includes the independent route-matching fix.
pnpm audit --audit-level high
if ($LASTEXITCODE -ne 0) { throw 'JavaScript dependency audit failed.' }

Write-Output 'Security scan passed without credential patterns or high-severity audit findings.'
