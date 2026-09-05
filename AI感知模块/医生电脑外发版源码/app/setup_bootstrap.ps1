try {
    $ErrorActionPreference = 'Stop'
    $env:DOCTOR_PACKAGE_ROOT = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
    $setupScript = Join-Path $PSScriptRoot 'doctor_setup.ps1'
    $source = [IO.File]::ReadAllText($setupScript, [Text.Encoding]::UTF8)
    & ([ScriptBlock]::Create($source))
} catch {
    if ($env:DOCTOR_SETUP_AUTOTEST -eq '1') {
        Write-Error $_
        exit 1
    }
    Add-Type -AssemblyName System.Windows.Forms
    [void][System.Windows.Forms.MessageBox]::Show(
        "Doctor model setup failed.`r`n`r`n" + $_.Exception.Message,
        'Doctor model setup',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    )
    exit 1
}
