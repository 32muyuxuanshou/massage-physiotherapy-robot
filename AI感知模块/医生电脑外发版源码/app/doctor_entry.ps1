$ErrorActionPreference = 'Stop'

$packageRoot = [IO.Path]::GetFullPath($env:DOCTOR_PACKAGE_ROOT)
$appRoot = Join-Path $packageRoot 'app'
$installState = Join-Path $packageRoot 'config\installation.json'

if (-not (Test-Path -LiteralPath $installState)) {
    $setupSource = [IO.File]::ReadAllText((Join-Path $appRoot 'doctor_setup.ps1'), [Text.Encoding]::UTF8)
    & ([ScriptBlock]::Create($setupSource))
}

if (-not (Test-Path -LiteralPath $installState)) {
    return
}

$env:DOCTOR_PORTABLE_MODE = '1'
$env:DOCTOR_LAUNCHER_ROOT = $packageRoot
$launcherSource = [IO.File]::ReadAllText((Join-Path $appRoot 'doctor_launcher.ps1'), [Text.Encoding]::UTF8)
& ([ScriptBlock]::Create($launcherSource))
