#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'

$distribution = 'Ubuntu-24.04'
$installRoot = 'E:\WSL'
$installLocation = Join-Path $installRoot $distribution
$logDirectory = Join-Path $PSScriptRoot 'logs'
$logPath = Join-Path $logDirectory 'install-wsl.log'

New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

"[$(Get-Date -Format o)] WSL staged installer started" |
    Out-File -LiteralPath $logPath -Append -Encoding UTF8

$wslFeature = Get-WindowsOptionalFeature `
    -Online `
    -FeatureName 'Microsoft-Windows-Subsystem-Linux'
$vmFeature = Get-WindowsOptionalFeature `
    -Online `
    -FeatureName 'VirtualMachinePlatform'

if ($wslFeature.State -ne 'Enabled' -or $vmFeature.State -ne 'Enabled') {
    "Stage=enable-features; WSL=$($wslFeature.State); VMPlatform=$($vmFeature.State)" |
        Out-File -LiteralPath $logPath -Append -Encoding UTF8

    $wslResult = Enable-WindowsOptionalFeature `
        -Online `
        -FeatureName 'Microsoft-Windows-Subsystem-Linux' `
        -All `
        -NoRestart
    $vmResult = Enable-WindowsOptionalFeature `
        -Online `
        -FeatureName 'VirtualMachinePlatform' `
        -All `
        -NoRestart

    "WSLRestartNeeded=$($wslResult.RestartNeeded); VMPlatformRestartNeeded=$($vmResult.RestartNeeded)" |
        Out-File -LiteralPath $logPath -Append -Encoding UTF8
    Write-Host 'WSL features enabled. Restart Windows, then run this same script again.'
    exit 0
}

if ((Test-Path -LiteralPath $installLocation) -and
    (Get-ChildItem -LiteralPath $installLocation -Force -ErrorAction SilentlyContinue)) {
    $installedDistributions = (& wsl.exe --list --quiet 2>$null) -join "`n"
    if ($installedDistributions -notmatch [regex]::Escape($distribution)) {
        throw "WSL target contains files but $distribution is not registered: $installLocation"
    }
    Write-Host "$distribution is already installed."
    exit 0
}

function Invoke-WslProcess {
    param(
        [Parameter(Mandatory)]
        [string[]]$Arguments,

        [Parameter(Mandatory)]
        [string]$Name,

        [switch]$AllowFailure
    )

    $stdoutPath = Join-Path $logDirectory "$Name.stdout.log"
    $stderrPath = Join-Path $logDirectory "$Name.stderr.log"
    $process = Start-Process `
        -FilePath "$env:SystemRoot\System32\wsl.exe" `
        -ArgumentList $Arguments `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -Wait `
        -PassThru
    "Stage=$Name; ExitCode=$($process.ExitCode)" |
        Out-File -LiteralPath $logPath -Append -Encoding UTF8
    if ($process.ExitCode -ne 0 -and -not $AllowFailure) {
        throw "WSL stage '$Name' failed with exit code $($process.ExitCode). See $stderrPath"
    }
    return $process.ExitCode
}

$versionExitCode = Invoke-WslProcess `
    -Name 'wsl-version-before-update' `
    -Arguments @('--version') `
    -AllowFailure
if ($versionExitCode -ne 0) {
    $updateExitCode = Invoke-WslProcess `
        -Name 'wsl-update-web' `
        -Arguments @('--update', '--web-download') `
        -AllowFailure
    if ($updateExitCode -ne 0) {
        "Web-download update was unavailable; trying the standard update channel." |
            Out-File -LiteralPath $logPath -Append -Encoding UTF8
        Invoke-WslProcess `
            -Name 'wsl-update-standard' `
            -Arguments @('--update')
    }

    Invoke-WslProcess `
        -Name 'wsl-version-after-update' `
        -Arguments @('--version')
} else {
    "A modern WSL runtime is already installed; update stage skipped." |
        Out-File -LiteralPath $logPath -Append -Encoding UTF8
}
Invoke-WslProcess `
    -Name 'wsl-default-version' `
    -Arguments @('--set-default-version', '2')
Invoke-WslProcess `
    -Name 'ubuntu-install' `
    -Arguments @(
        '--install',
        '--distribution', $distribution,
        '--location', $installLocation,
        '--no-launch',
        '--web-download'
    )

Write-Host "WSL and $distribution installation completed. Verify with: wsl --version and wsl -l -v"
