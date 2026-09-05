#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'

$interfaceIndex = 17
$serverAddress = '1.12.12.12'
$dohTemplate = 'https://doh.pub/dns-query'
$logPath = Join-Path $PSScriptRoot 'logs\network-dns-change.log'

New-Item -ItemType Directory -Path (Split-Path -Parent $logPath) -Force | Out-Null
$originalServers = (Get-DnsClientServerAddress `
    -InterfaceIndex $interfaceIndex `
    -AddressFamily IPv4).ServerAddresses

"[$(Get-Date -Format o)] Before=$($originalServers -join ','); Target=$serverAddress; DoH=$dohTemplate" |
    Out-File -LiteralPath $logPath -Append -Encoding UTF8

try {
    $existing = Get-DnsClientDohServerAddress `
        -ServerAddress $serverAddress `
        -ErrorAction SilentlyContinue
    if ($existing) {
        Set-DnsClientDohServerAddress `
            -ServerAddress $serverAddress `
            -DohTemplate $dohTemplate `
            -AllowFallbackToUdp $false `
            -AutoUpgrade $true | Out-Null
    } else {
        Add-DnsClientDohServerAddress `
            -ServerAddress $serverAddress `
            -DohTemplate $dohTemplate `
            -AllowFallbackToUdp $false `
            -AutoUpgrade $true
    }

    Set-DnsClientServerAddress `
        -InterfaceIndex $interfaceIndex `
        -ServerAddresses $serverAddress
    Clear-DnsClientCache

    $addresses = Resolve-DnsName auth.docker.io -Type A |
        Where-Object Type -eq 'A' |
        Select-Object -ExpandProperty IPAddress
    $httpCode = & "$env:SystemRoot\System32\curl.exe" `
        -4 `
        --silent `
        --show-error `
        --max-time 20 `
        --output NUL `
        --write-out '%{http_code}' `
        'https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/python:pull'
    if ($LASTEXITCODE -ne 0 -or $httpCode -ne '200') {
        throw "Docker Hub HTTPS validation failed. curl=$LASTEXITCODE; HTTP=$httpCode"
    }

    "After=$($addresses -join ','); HTTP=$httpCode; Result=OK" |
        Out-File -LiteralPath $logPath -Append -Encoding UTF8
    Write-Host "DNS over HTTPS enabled. auth.docker.io=$($addresses -join ','); HTTP=$httpCode"
} catch {
    Set-DnsClientServerAddress -InterfaceIndex $interfaceIndex -ResetServerAddresses
    Clear-DnsClientCache
    "Result=ROLLED_BACK; Error=$($_.Exception.Message)" |
        Out-File -LiteralPath $logPath -Append -Encoding UTF8
    throw
}
