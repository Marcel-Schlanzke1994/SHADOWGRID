Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-ShadowgridProjectRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

function Get-ShadowgridRunRoot {
    $runRoot = Join-Path (Get-ShadowgridProjectRoot) '.local\run'
    New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
    return $runRoot
}

function Resolve-ShadowgridMode {
    param(
        [ValidateSet('Auto', 'Compose', 'SQLite')]
        [string]$Mode = 'Auto'
    )

    if ($Mode -ne 'Auto') {
        if ($Mode -eq 'Compose' -and -not (Get-Command docker -ErrorAction SilentlyContinue)) {
            throw 'Compose mode requires Docker Desktop with the Compose plugin.'
        }
        return $Mode
    }

    $runRoot = Get-ShadowgridRunRoot
    if (Get-ChildItem -LiteralPath $runRoot -Filter '*.pid.json' -File -ErrorAction SilentlyContinue) {
        return 'SQLite'
    }
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        return 'Compose'
    }
    return 'SQLite'
}

function Get-ShadowgridEnvValue {
    param(
        [Parameter(Mandatory)]
        [string]$Name,
        [Parameter(Mandatory)]
        [string]$Default
    )

    $envFile = Join-Path (Get-ShadowgridProjectRoot) '.local\development.env'
    if (-not (Test-Path -LiteralPath $envFile)) {
        return $Default
    }
    $line = Get-Content -LiteralPath $envFile |
        Where-Object { $_ -match "^\s*$([regex]::Escape($Name))\s*=" } |
        Select-Object -Last 1
    if ($null -eq $line) {
        return $Default
    }
    return ($line -split '=', 2)[1].Trim()
}

function Wait-ShadowgridHttp {
    param(
        [Parameter(Mandatory)]
        [string]$Uri,
        [int]$TimeoutSeconds = 90
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                return
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
    } while ((Get-Date) -lt $deadline)
    throw "Timed out waiting for $Uri"
}

function Start-ShadowgridManagedProcess {
    param(
        [Parameter(Mandatory)]
        [string]$Name,
        [Parameter(Mandatory)]
        [string]$FilePath,
        [Parameter(Mandatory)]
        [string[]]$ArgumentList,
        [Parameter(Mandatory)]
        [string]$WorkingDirectory,
        [Parameter(Mandatory)]
        [string]$Marker
    )

    $runRoot = Get-ShadowgridRunRoot
    $pidPath = Join-Path $runRoot "$Name.pid.json"
    if (Test-Path -LiteralPath $pidPath) {
        $existing = Get-Content -LiteralPath $pidPath -Raw | ConvertFrom-Json
        if (Get-Process -Id ([int]$existing.pid) -ErrorAction SilentlyContinue) {
            Write-Output "$Name is already running with PID $($existing.pid)."
            return
        }
        Remove-Item -LiteralPath $pidPath -Force
    }

    $stdoutPath = Join-Path $runRoot "$Name.stdout.log"
    $stderrPath = Join-Path $runRoot "$Name.stderr.log"
    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -PassThru
    @{
        pid = $process.Id
        marker = $Marker
        process_name = $process.ProcessName
        process_started_at = $process.StartTime.ToUniversalTime().ToString('o')
        process_started_at_ticks = $process.StartTime.ToUniversalTime().Ticks
        recorded_at = (Get-Date).ToUniversalTime().ToString('o')
    } | ConvertTo-Json | Set-Content -LiteralPath $pidPath -Encoding utf8
    Write-Output "Started $Name with PID $($process.Id)."
}

function Test-ShadowgridManagedProcess {
    param(
        [Parameter(Mandatory)]
        [string]$Name
    )

    $pidPath = Join-Path (Get-ShadowgridRunRoot) "$Name.pid.json"
    if (-not (Test-Path -LiteralPath $pidPath)) {
        return $false
    }
    $record = Get-Content -LiteralPath $pidPath -Raw | ConvertFrom-Json
    return $null -ne (Get-Process -Id ([int]$record.pid) -ErrorAction SilentlyContinue)
}

function Stop-ShadowgridManagedProcess {
    param(
        [Parameter(Mandatory)]
        [string]$Name
    )

    $pidPath = Join-Path (Get-ShadowgridRunRoot) "$Name.pid.json"
    if (-not (Test-Path -LiteralPath $pidPath)) {
        Write-Output "$Name is not recorded as running."
        return
    }
    $record = Get-Content -LiteralPath $pidPath -Raw | ConvertFrom-Json
    $processId = [int]$record.pid
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        Remove-Item -LiteralPath $pidPath -Force
        Write-Output "Removed stale $Name PID record."
        return
    }
    $hasTickRecord = $record.PSObject.Properties.Name -contains 'process_started_at_ticks'
    $hasNameRecord = $record.PSObject.Properties.Name -contains 'process_name'
    $recordedTicks = if ($hasTickRecord) {
        [long]$record.process_started_at_ticks
    } else {
        ([datetime]$record.process_started_at).ToUniversalTime().Ticks
    }
    $nameMatches = -not $hasNameRecord -or
        [string]$process.ProcessName -eq [string]$record.process_name
    if (-not $nameMatches -or $process.StartTime.ToUniversalTime().Ticks -ne $recordedTicks) {
        throw "Refusing to stop PID $processId because its executable identity does not match $Name."
    }

    $taskkill = Join-Path $env:WINDIR 'System32\taskkill.exe'
    & $taskkill /PID $processId /T /F | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to stop the validated $Name process tree."
    }
    Remove-Item -LiteralPath $pidPath -Force
    Write-Output "Stopped $Name."
}
