try {
    $ErrorActionPreference = 'Stop'
    $buildScript = Join-Path $PSScriptRoot 'build_doctor_portable_body_distribution.ps1'
    $source = [IO.File]::ReadAllText($buildScript, [Text.Encoding]::UTF8)
    $oldLocation = Get-Location
    try {
        Set-Location $PSScriptRoot
        & ([ScriptBlock]::Create($source))
    } finally {
        Set-Location $oldLocation
    }
} catch {
    Write-Error $_
    exit 1
}
