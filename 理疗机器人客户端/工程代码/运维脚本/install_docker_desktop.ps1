$ErrorActionPreference = 'Stop'

$installer = Join-Path $PSScriptRoot 'downloads\docker-desktop-4.86.0.exe'
$expectedHash = '820438E75C16E44B393079154BEA7D27958A15845C23A635B1A1F6F586B2ED44'
$dataRoot = 'E:\Docker\wsl'
$logDirectory = Join-Path $PSScriptRoot 'logs'
$logPath = Join-Path $logDirectory 'install-docker-desktop.log'

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
    throw "Docker Desktop installer not found: $installer"
}

$actualHash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash
if ($actualHash -ne $expectedHash) {
    throw "Docker Desktop installer hash mismatch. Expected $expectedHash; got $actualHash"
}

$signature = Get-AuthenticodeSignature -LiteralPath $installer
if ($signature.Status -ne 'Valid' -or
    $signature.SignerCertificate.Subject -notmatch 'CN=Docker Inc') {
    throw "Docker Desktop installer signature is not valid Docker Inc. Status=$($signature.Status)"
}

"[$(Get-Date -Format o)] Installing Docker Desktop 4.86.0; DataRoot=$dataRoot" |
    Out-File -LiteralPath $logPath -Append -Encoding UTF8

$arguments = @(
    'install'
    '--user'
    '--quiet'
    '--backend=wsl-2'
    "--wsl-default-data-root=$dataRoot"
    '--no-windows-containers'
)
$process = Start-Process `
    -FilePath $installer `
    -ArgumentList $arguments `
    -Wait `
    -PassThru

"ExitCode=$($process.ExitCode)" |
    Out-File -LiteralPath $logPath -Append -Encoding UTF8
if ($process.ExitCode -ne 0) {
    throw "Docker Desktop installation failed with exit code $($process.ExitCode)."
}

Write-Host 'Docker Desktop installation completed. The license has not been accepted automatically.'
