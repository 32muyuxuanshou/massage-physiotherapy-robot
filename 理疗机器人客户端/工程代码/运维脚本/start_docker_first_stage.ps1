$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$environmentFile = Join-Path $projectRoot '.env.docker'
$dockerBin = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin'
$docker = Join-Path $dockerBin 'docker.exe'

if (-not (Test-Path -LiteralPath $docker -PathType Leaf)) {
    throw "Docker CLI not found: $docker"
}

if (-not (Test-Path -LiteralPath $environmentFile -PathType Leaf)) {
    $randomBytes = New-Object byte[] 48
    $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $random.GetBytes($randomBytes)
    } finally {
        $random.Dispose()
    }
    $secret = -join ($randomBytes | ForEach-Object { $_.ToString('x2') })
    $content = @(
        "SECRET_KEY=$secret"
        'APP_BIND_ADDRESS=127.0.0.1'
        'APP_PORT=8080'
    ) -join [Environment]::NewLine
    $utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($environmentFile, $content + [Environment]::NewLine, $utf8WithoutBom)
    Write-Host 'Created .env.docker with a random local secret (value not displayed).'
}

$previousDockerStartPath = $env:Path
try {
    $env:Path = "$dockerBin;$previousDockerStartPath"
    Push-Location $projectRoot
    try {
        & $docker compose --env-file $environmentFile config --quiet
        if ($LASTEXITCODE -ne 0) {
            throw 'Docker Compose configuration validation failed.'
        }

        & $docker compose --env-file $environmentFile up -d --build
        if ($LASTEXITCODE -ne 0) {
            throw 'Docker Compose build or startup failed.'
        }
    } finally {
        Pop-Location
    }
} finally {
    $env:Path = $previousDockerStartPath
}

Write-Host 'First-stage containers started at http://127.0.0.1:8080'
