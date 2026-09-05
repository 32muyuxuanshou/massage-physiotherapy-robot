#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'

$interfaceIndex = 17
$serverAddress = '1.12.12.12'
$logPath = Join-Path $PSScriptRoot 'logs\network-dns-change.log'

Set-DnsClientServerAddress -InterfaceIndex $interfaceIndex -ResetServerAddresses
Clear-DnsClientCache

$existing = Get-DnsClientDohServerAddress `
    -ServerAddress $serverAddress `
    -ErrorAction SilentlyContinue
if ($existing) {
    Remove-DnsClientDohServerAddress -ServerAddress $serverAddress | Out-Null
}

$restoredServers = (Get-DnsClientServerAddress `
    -InterfaceIndex $interfaceIndex `
    -AddressFamily IPv4).ServerAddresses
"[$(Get-Date -Format o)] Restored DHCP DNS=$($restoredServers -join ',')" |
    Out-File -LiteralPath $logPath -Append -Encoding UTF8
Write-Host "DHCP DNS restored: $($restoredServers -join ',')"
