param(
    [Parameter(Position = 0)]
    [ValidateSet('setup', 'dev', 'migrate', 'seed', 'test', 'test-e2e', 'lint', 'typecheck', 'security', 'validate', 'reset-local', 'logs', 'stop', 'clean')]
    [string]$Action = 'validate'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

function Invoke-Step([string]$Name, [scriptblock]$Command) {
    Write-Output "== $Name =="
    $global:LASTEXITCODE = 0
    & $Command
    if (-not $?) { throw "$Name failed in PowerShell." }
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
}

function Ensure-Setup {
    Invoke-Step 'Environment check' { & "$PSScriptRoot\check-environment.ps1" }
    if (-not (Test-Path $venvPython)) {
        Invoke-Step 'Create Python virtual environment' { python -m venv "$projectRoot\.venv" }
    }
    Invoke-Step 'Install Python dependencies' { & $venvPython -m pip install --disable-pip-version-check -r "$projectRoot\apps\api\requirements-dev.txt" }
    Invoke-Step 'Install workspace dependencies' { pnpm install --frozen-lockfile=$false }
    Invoke-Step 'Generate local secrets' { & $venvPython "$PSScriptRoot\generate-local-secrets.py" }
}

Set-Location $projectRoot
switch ($Action) {
    'setup' {
        Ensure-Setup
        Invoke-Step 'Migrate database' { pnpm migrate }
        Invoke-Step 'Seed local world' { pnpm seed }
    }
    'dev' { pnpm dev }
    'migrate' { pnpm migrate }
    'seed' { pnpm seed }
    'test' { pnpm test }
    'test-e2e' { pnpm test:e2e }
    'lint' { pnpm lint }
    'typecheck' { pnpm typecheck }
    'security' { pnpm test:security }
    'logs' { pnpm logs }
    'stop' { pnpm stop }
    'clean' {
        foreach ($path in @(
            'dist',
            'coverage',
            'playwright-report',
            'test-results',
            'apps\api\.coverage',
            'apps\mobile\coverage',
            'apps\mobile\dist',
            'apps\web\coverage',
            'apps\web\dist',
            'apps\web\playwright-report',
            'apps\web\test-results'
        )) {
            $target = Join-Path $projectRoot $path
            if ((Test-Path $target) -and ((Resolve-Path $target).Path.StartsWith($projectRoot))) {
                Remove-Item -LiteralPath $target -Recurse -Force
            }
        }
    }
    'reset-local' {
        $db = Join-Path $projectRoot '.local\shadowgrid.db'
        if (Test-Path $db) { Remove-Item -LiteralPath $db -Force }
        pnpm migrate
        pnpm seed
    }
    'validate' {
        Ensure-Setup
        Invoke-Step 'Migration' { pnpm migrate }
        Invoke-Step 'Seed' { pnpm seed }
        Invoke-Step 'Generate API client' { pnpm api:generate }
        Invoke-Step 'Localization' { pnpm i18n:validate }
        Invoke-Step 'Formatting' { pnpm format:check }
        Invoke-Step 'Lint' { pnpm lint }
        Invoke-Step 'Typecheck' { pnpm typecheck }
        Invoke-Step 'Tests' { pnpm test }
        Invoke-Step 'Load smoke test' { pnpm test:load }
        Invoke-Step 'Security' { pnpm test:security }
        Invoke-Step 'Production builds' { pnpm build }
        Invoke-Step 'Browser end-to-end tests' { pnpm test:e2e }
    }
}
