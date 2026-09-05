try {
    $ErrorActionPreference = 'Stop'
    $env:DOCTOR_PACKAGE_ROOT = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
    $entryScript = Join-Path $PSScriptRoot 'doctor_entry.ps1'
    $source = [IO.File]::ReadAllText($entryScript, [Text.Encoding]::UTF8)
    & ([ScriptBlock]::Create($source))
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [void][System.Windows.Forms.MessageBox]::Show(
        "Doctor workbench failed.`r`n`r`n" + $_.Exception.Message,
        'Doctor annotation workbench',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    )
    exit 1
}
