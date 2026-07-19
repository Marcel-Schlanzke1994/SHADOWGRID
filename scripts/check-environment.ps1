$ErrorActionPreference = 'Stop'

$requirements = @(
    @{ Name = 'Git'; Command = 'git'; Required = $true },
    @{ Name = 'Node.js'; Command = 'node'; Required = $true },
    @{ Name = 'pnpm'; Command = 'pnpm'; Required = $true },
    @{ Name = 'Python'; Command = 'python'; Required = $true },
    @{ Name = 'Docker'; Command = 'docker'; Required = $false },
    @{ Name = 'Java'; Command = 'java'; Required = $false },
    @{ Name = 'Android Debug Bridge'; Command = 'adb'; Required = $false }
)

$missingRequired = $false
foreach ($item in $requirements) {
    $command = Get-Command $item.Command -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        $level = if ($item.Required) { 'REQUIRED' } else { 'OPTIONAL' }
        Write-Output "[$level] $($item.Name): missing"
        if ($item.Required) { $missingRequired = $true }
    } else {
        Write-Output "[OK] $($item.Name): $($command.Source)"
    }
}

$memoryGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
Write-Output "[INFO] CPU: $($cpu.Name), $($cpu.NumberOfLogicalProcessors) logical processors"
Write-Output "[INFO] RAM: $memoryGb GB"

if ($missingRequired) {
    throw 'One or more required local prerequisites are missing.'
}

Write-Output '[OK] Required native prerequisites are available.'
