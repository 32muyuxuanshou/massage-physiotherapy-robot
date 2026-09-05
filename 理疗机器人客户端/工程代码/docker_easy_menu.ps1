param(
    [ValidateSet('menu', 'deploy', 'start', 'stop', 'status', 'logs', 'open', 'selftest')]
    [string]$Action = 'menu'
)

$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
$composeFile = Join-Path $projectRoot 'docker-compose.yml'
$environmentFile = Join-Path $projectRoot '.env.docker'
$projectLogDirectory = Join-Path $projectRoot 'logs'
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$sessionLog = Join-Path $projectLogDirectory "docker-easy-menu-$timestamp.log"
$applicationUrl = 'http://127.0.0.1:8080'
$healthUrl = 'http://127.0.0.1:8080/health'
$dockerHubTokenUrl = 'https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/python:pull'
$flClashProxyUrl = 'http://127.0.0.1:7890'
$script:activeNetworkProxyUrl = $null
$requiredImages = @(
    'python:3.11-slim'
    'node:22-alpine'
    'nginx:1.28-alpine'
)

New-Item -ItemType Directory -Path $projectLogDirectory -Force | Out-Null

function Find-DockerCli {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe')
        (Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin\docker.exe')
    )
    $command = Get-Command docker.exe -ErrorAction SilentlyContinue
    if ($command) {
        $candidates += $command.Source
    }
    return $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
}

function Find-DockerDesktop {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe')
        (Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe')
    )
    return $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}

$docker = Find-DockerCli
if (-not $docker) {
    Write-Host 'Docker CLI was not found. Install Docker Desktop first.' -ForegroundColor Red
    Write-Host 'See the Docker Markdown tutorial in the project root.'
    exit 1
}
$dockerBin = Split-Path -Parent $docker
$previousEasyMenuPath = $env:Path
$env:Path = "$dockerBin;$previousEasyMenuPath"

$startScript = Get-ChildItem -LiteralPath $projectRoot -Directory |
    ForEach-Object { Join-Path $_.FullName 'start_docker_first_stage.ps1' } |
    Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
    Select-Object -First 1
if (-not $startScript) {
    Write-Host 'start_docker_first_stage.ps1 was not found.' -ForegroundColor Red
    exit 1
}

$transcriptStarted = $false
try {
    Start-Transcript -LiteralPath $sessionLog -Append | Out-Null
    $transcriptStarted = $true
} catch {
    Write-Host "Warning: could not start transcript: $($_.Exception.Message)" -ForegroundColor Yellow
}

function Write-Section {
    param([Parameter(Mandatory)][string]$Title)
    Write-Host ''
    Write-Host "==== $Title ====" -ForegroundColor Cyan
}

function Ensure-EnvironmentFile {
    if (Test-Path -LiteralPath $environmentFile -PathType Leaf) {
        return
    }

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
    [System.IO.File]::WriteAllText(
        $environmentFile,
        $content + [Environment]::NewLine,
        $utf8WithoutBom
    )
    Write-Host 'Created .env.docker with a random secret. The value was not displayed.' -ForegroundColor Green
}

function Invoke-Compose {
    param(
        [Parameter(Mandatory)][string[]]$Arguments,
        [switch]$AllowFailure
    )

    $temporarySecret = $false
    if (Test-Path -LiteralPath $environmentFile -PathType Leaf) {
        $composeArguments = @('compose', '--env-file', $environmentFile, '-f', $composeFile) + $Arguments
    } else {
        $env:SECRET_KEY = 'temporary-value-used-only-to-parse-compose'
        $temporarySecret = $true
        $composeArguments = @('compose', '-f', $composeFile) + $Arguments
    }

    try {
        & $docker @composeArguments
        $composeExit = $LASTEXITCODE
    } finally {
        if ($temporarySecret) {
            Remove-Item Env:SECRET_KEY -ErrorAction SilentlyContinue
        }
    }

    if ($composeExit -ne 0 -and -not $AllowFailure) {
        throw "Docker Compose failed with exit code $composeExit."
    }
    if ($AllowFailure) {
        return $composeExit
    }
}

function Test-DockerEngine {
    $result = & $docker info --format '{{.ServerVersion}}' 2>&1
    return ($LASTEXITCODE -eq 0 -and $result)
}

function Wait-DockerEngine {
    param([int]$TimeoutSeconds = 120)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-DockerEngine) {
            Write-Host 'Docker Engine is ready.' -ForegroundColor Green
            return
        }
        Write-Host -NoNewline '.'
        Start-Sleep -Seconds 3
    }
    throw "Docker Engine did not become ready within $TimeoutSeconds seconds."
}

function Ensure-DockerEngine {
    if (Test-DockerEngine) {
        return
    }

    $desktop = Find-DockerDesktop
    if (-not $desktop) {
        throw 'Docker Desktop application was not found.'
    }
    Write-Host 'Starting Docker Desktop...'
    Start-Process -FilePath $desktop | Out-Null
    Wait-DockerEngine
}

function Test-DockerHubFromWindows {
    param(
        [string]$ProxyUrl,
        [switch]$QuietFailure
    )

    $curl = Join-Path $env:SystemRoot 'System32\curl.exe'
    if (-not (Test-Path -LiteralPath $curl -PathType Leaf)) {
        throw 'Windows curl.exe was not found.'
    }

    # Windows PowerShell 5 can turn curl stderr into a terminating error when
    # the script-wide preference is Stop. A failed network probe must return
    # false so the user can change networks and retry instead of exiting.
    $savedErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $curlArguments = @(
            '-4'
            '--silent'
            '--show-error'
            '--connect-timeout', '10'
            '--max-time', '25'
            '--output', 'NUL'
            '--write-out', '%{http_code}'
        )
        if ($ProxyUrl) {
            $curlArguments += @('--proxy', $ProxyUrl)
        }
        $curlArguments += $dockerHubTokenUrl
        $result = & $curl @curlArguments 2>&1
        $curlExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
    $resultText = ($result -join ' ').Trim()
    $routeLabel = if ($ProxyUrl) { "proxy $ProxyUrl" } else { 'direct network' }
    if ($curlExit -eq 0 -and $resultText -eq '200') {
        Write-Host "Docker Hub authentication endpoint: OK via $routeLabel (HTTP 200)." -ForegroundColor Green
        return $true
    }

    if (-not $QuietFailure) {
        Write-Host "Docker Hub authentication endpoint: FAILED via $routeLabel (curl=$curlExit, result=$resultText)" -ForegroundColor Red
    }
    return $false
}

function Enable-FlClashSystemProxy {
    $proxyKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
    $settings = Get-ItemProperty -LiteralPath $proxyKey
    $expectedServer = '127.0.0.1:7890'

    if ($settings.ProxyEnable -eq 1 -and $settings.ProxyServer -eq $expectedServer) {
        Write-Host 'Windows system proxy already points to FlClash 127.0.0.1:7890.' -ForegroundColor Green
        return
    }
    if ($settings.ProxyEnable -eq 1 -and $settings.ProxyServer -and $settings.ProxyServer -ne $expectedServer) {
        throw "Another Windows system proxy is enabled: $($settings.ProxyServer). It was not overwritten."
    }

    Set-ItemProperty -LiteralPath $proxyKey -Name ProxyEnable -Type DWord -Value 1
    Set-ItemProperty -LiteralPath $proxyKey -Name ProxyServer -Type String -Value $expectedServer
    Set-ItemProperty -LiteralPath $proxyKey -Name ProxyOverride -Type String -Value '<local>;127.0.0.1;localhost'
    Write-Host 'Enabled Windows system proxy for Docker Desktop: 127.0.0.1:7890.' -ForegroundColor Green
}

function Wait-ForUsableNetwork {
    Write-Section 'NETWORK CHECK'
    Write-Host 'Keep FlClash running and connected during the first build.' -ForegroundColor Yellow
    Write-Host 'This tool tries the direct network first, then FlClash 127.0.0.1:7890.'

    while ($true) {
        try {
            Clear-DnsClientCache -ErrorAction SilentlyContinue
        } catch {
        }
        if (Test-DockerHubFromWindows -QuietFailure) {
            $script:activeNetworkProxyUrl = $null
            return
        }
        if (Test-DockerHubFromWindows -ProxyUrl $flClashProxyUrl -QuietFailure) {
            Enable-FlClashSystemProxy
            $script:activeNetworkProxyUrl = $flClashProxyUrl
            return
        }

        Write-Host ''
        Write-Host 'Neither the direct network nor FlClash 127.0.0.1:7890 can reach Docker Hub.' -ForegroundColor Red
        Write-Host 'Open FlClash, connect a working node, and keep the FlClash core running.'
        Write-Host 'A phone hotspot is only the fallback when FlClash is unavailable.' -ForegroundColor Yellow
        $answer = Read-Host 'Enter R to retry, or Q to cancel'
        if ($answer.Trim().ToUpperInvariant() -eq 'Q') {
            throw 'Deployment cancelled because Docker Hub is not reachable.'
        }
    }
}

function Pull-RequiredImages {
    Write-Section 'OFFICIAL BASE IMAGES'
    foreach ($image in $requiredImages) {
        Write-Host "Pulling $image ..."
        & $docker pull $image
        if ($LASTEXITCODE -ne 0) {
            throw "Could not pull $image. Keep FlClash connected and retry option 1."
        }
    }
}

function Wait-ApplicationHealth {
    param([int]$TimeoutSeconds = 180)

    Write-Host "Waiting for $healthUrl ..."
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) {
                Write-Host 'Application health check: OK (HTTP 200).' -ForegroundColor Green
                return
            }
        } catch {
        }
        Write-Host -NoNewline '.'
        Start-Sleep -Seconds 3
    }
    throw "Application did not become healthy within $TimeoutSeconds seconds."
}

function Invoke-FirstDeployment {
    Wait-ForUsableNetwork
    Ensure-DockerEngine

    if ($script:activeNetworkProxyUrl) {
        $networkReady = Test-DockerHubFromWindows -ProxyUrl $script:activeNetworkProxyUrl
    } else {
        $networkReady = Test-DockerHubFromWindows
    }
    if (-not $networkReady) {
        throw 'Docker Hub became unreachable before the image pull started.'
    }

    Pull-RequiredImages
    Ensure-EnvironmentFile

    Write-Section 'BUILD AND START'
    & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $startScript
    if ($LASTEXITCODE -ne 0) {
        throw "The build/start script failed with exit code $LASTEXITCODE."
    }

    Wait-ApplicationHealth
    Invoke-Compose -Arguments @('ps') | Out-Host
    Write-Host ''
    Write-Host 'DEPLOYMENT PASSED.' -ForegroundColor Green
    Write-Host "Open: $applicationUrl"
    Write-Host 'Daily start can now work from the cached local images without internet.' -ForegroundColor Green
    Start-Process $applicationUrl | Out-Null
}

function Start-ExistingDeployment {
    Ensure-EnvironmentFile
    Ensure-DockerEngine
    Invoke-Compose -Arguments @('up', '-d', '--no-build', '--pull', 'never') | Out-Host
    Wait-ApplicationHealth
    Write-Host "Application started: $applicationUrl" -ForegroundColor Green
}

function Stop-ExistingDeployment {
    if (-not (Test-DockerEngine)) {
        Write-Host 'Docker Engine is already stopped; the application is not running.' -ForegroundColor Yellow
        return
    }
    Invoke-Compose -Arguments @('down') | Out-Host
    Write-Host 'Application containers stopped. Database volumes were preserved.' -ForegroundColor Green
}

function Show-DeploymentStatus {
    Ensure-DockerEngine
    Invoke-Compose -Arguments @('ps') | Out-Host
    try {
        $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5
        Write-Host "Health: HTTP $($response.StatusCode)" -ForegroundColor Green
    } catch {
        Write-Host 'Health: not reachable.' -ForegroundColor Yellow
    }
}

function Show-DeploymentLogs {
    Ensure-DockerEngine
    Invoke-Compose -Arguments @('logs', '--tail', '100') | Out-Host
}

function Open-Application {
    Start-Process $applicationUrl | Out-Null
    Write-Host "Opened $applicationUrl"
}

function Invoke-SelfTest {
    Write-Section 'SELF TEST'
    if (-not (Test-Path -LiteralPath $composeFile -PathType Leaf)) {
        throw "Missing compose file: $composeFile"
    }
    if (-not (Test-Path -LiteralPath $startScript -PathType Leaf)) {
        throw "Missing start script: $startScript"
    }
    [void](Invoke-Compose -Arguments @('config', '--quiet'))
    Write-Host "Docker CLI: $docker"
    Write-Host "Compose file: $composeFile"
    Write-Host "Start script: $startScript"
    Write-Host 'SELF TEST PASSED.' -ForegroundColor Green
}

function Pause-EasyMenu {
    [void](Read-Host 'Press ENTER to return to the menu')
}

function Show-EasyMenu {
    while ($true) {
        Clear-Host
        Write-Host 'Physiotherapy Client - Docker Easy Menu' -ForegroundColor Cyan
        Write-Host ''
        Write-Host '1  First build / rebuild (keep FlClash connected)'
        Write-Host '2  Start existing containers (usually no internet needed)'
        Write-Host '3  Stop containers (database is preserved)'
        Write-Host '4  Show status and health'
        Write-Host '5  Open application in browser'
        Write-Host '6  Show last 100 log lines'
        Write-Host '0  Exit'
        Write-Host ''
        $choice = Read-Host 'Choose'

        try {
            switch ($choice.Trim()) {
                '1' { Invoke-FirstDeployment; Pause-EasyMenu }
                '2' { Start-ExistingDeployment; Pause-EasyMenu }
                '3' { Stop-ExistingDeployment; Pause-EasyMenu }
                '4' { Show-DeploymentStatus; Pause-EasyMenu }
                '5' { Open-Application; Pause-EasyMenu }
                '6' { Show-DeploymentLogs; Pause-EasyMenu }
                '0' { return }
                default { Write-Host 'Invalid choice.' -ForegroundColor Yellow; Start-Sleep -Seconds 1 }
            }
        } catch {
            Write-Host ''
            Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "Log: $sessionLog" -ForegroundColor Yellow
            Pause-EasyMenu
        }
    }
}

try {
    switch ($Action) {
        'deploy' { Invoke-FirstDeployment }
        'start' { Start-ExistingDeployment }
        'stop' { Stop-ExistingDeployment }
        'status' { Show-DeploymentStatus }
        'logs' { Show-DeploymentLogs }
        'open' { Open-Application }
        'selftest' { Invoke-SelfTest }
        default { Show-EasyMenu }
    }
} finally {
    $env:Path = $previousEasyMenuPath
    if ($transcriptStarted) {
        Stop-Transcript | Out-Null
    }
}
