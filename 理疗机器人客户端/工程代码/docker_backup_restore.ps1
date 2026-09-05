param(
    [ValidateSet('menu', 'full', 'backup', 'drill', 'status')]
    [string]$Action = 'menu',
    [string]$BackupFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
$composeFile = Join-Path $projectRoot 'docker-compose.yml'
$environmentFile = Join-Path $projectRoot '.env.docker'
$backupRoot = Join-Path $projectRoot 'backups\docker-sqlite'
$logRoot = Join-Path $projectRoot 'logs'
$dockerBin = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin'
$docker = Join-Path $dockerBin 'docker.exe'
$localPython = Join-Path $projectRoot 'backend\.venv\Scripts\python.exe'
$databasePath = '/app/data/physiotherapy.db'

[void][System.IO.Directory]::CreateDirectory($logRoot)
$sessionStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$sessionLog = Join-Path $logRoot "docker-backup-$sessionStamp.log"
$transcriptStarted = $false
$previousPath = $env:Path

function Write-Section {
    param([string]$Title)
    Write-Host ''
    Write-Host "==== $Title ====" -ForegroundColor Cyan
}

function Assert-File {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label not found: $Path"
    }
}

function Invoke-DockerCapture {
    param([string[]]$DockerArgs)
    $output = & $script:docker @DockerArgs 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Docker command failed ($exitCode): docker $($DockerArgs -join ' ')`n$($output -join [Environment]::NewLine)"
    }
    return (($output -join [Environment]::NewLine).Trim())
}

function Test-DockerReady {
    $savedPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $script:docker info --format '{{.ServerVersion}}' 2>&1 | Out-Null
        return ($LASTEXITCODE -eq 0)
    } finally {
        $ErrorActionPreference = $savedPreference
    }
}

function Ensure-DockerReady {
    if (Test-DockerReady) {
        return
    }

    Write-Host 'Docker Desktop is not ready. Starting it now...' -ForegroundColor Yellow
    [void](Invoke-DockerCapture -DockerArgs @('desktop', 'start'))
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if (Test-DockerReady) {
            Write-Host 'Docker Desktop is ready.' -ForegroundColor Green
            return
        }
        Start-Sleep -Seconds 2
    }
    throw 'Docker Desktop did not become ready within 120 seconds.'
}

function Invoke-ContainerPython {
    param([string]$ContainerId, [string]$PythonCode)
    $output = $PythonCode | & $script:docker exec -i $ContainerId python - 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Python in container failed ($exitCode):`n$($output -join [Environment]::NewLine)"
    }
    return (($output -join [Environment]::NewLine).Trim())
}

function Test-LocalDatabase {
    param([string]$Path)
    Assert-File -Path $Path -Label 'Backup database'
    $pythonCode = @'
import hashlib
import json
import os
import sqlite3
import sys

path = sys.argv[1]
connection = sqlite3.connect("file:" + path + "?mode=ro", uri=True)
tables = [row[0] for row in connection.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name")]
counts = {table: connection.execute('select count(*) from "' + table.replace('"', '""') + '"').fetchone()[0] for table in tables}
integrity = connection.execute("pragma integrity_check").fetchone()[0]
connection.close()

digest = hashlib.sha256()
with open(path, "rb") as stream:
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)

print(json.dumps({"bytes": os.path.getsize(path), "counts": counts, "integrity": integrity, "sha256": digest.hexdigest(), "tables": tables}, sort_keys=True))
'@
    $output = $pythonCode | & $script:localPython - $Path 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Local backup validation failed ($exitCode):`n$($output -join [Environment]::NewLine)"
    }
    $result = ($output -join [Environment]::NewLine) | ConvertFrom-Json
    if ($result.integrity -ne 'ok') {
        throw "SQLite integrity check failed: $($result.integrity)"
    }
    return $result
}

function Get-BackendState {
    $containerId = Invoke-DockerCapture -DockerArgs @(
        'compose', '--project-directory', $projectRoot, '-f', $composeFile,
        '--env-file', $environmentFile, 'ps', '-q', 'backend'
    )
    if ([string]::IsNullOrWhiteSpace($containerId)) {
        throw 'The backend container is not running. Start the deployment with Docker_One_Click.cmd option 2.'
    }

    $containerStatus = Invoke-DockerCapture -DockerArgs @('inspect', '--format', '{{.State.Status}}', $containerId)
    if ($containerStatus -ne 'running') {
        throw "The backend container is not running: $containerStatus"
    }
    $healthStatus = Invoke-DockerCapture -DockerArgs @('inspect', '--format', '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}', $containerId)
    if ($healthStatus -ne 'none' -and $healthStatus -ne 'healthy') {
        throw "The backend container is not healthy: $healthStatus"
    }

    $mountOutput = Invoke-DockerCapture -DockerArgs @('inspect', '--format', '{{range .Mounts}}{{println .Name .Destination .Type}}{{end}}', $containerId)
    $dataMountLine = @($mountOutput -split "`r?`n" | Where-Object { $_ -match '\s/app/data\s+volume\s*$' }) | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($dataMountLine)) {
        throw 'The /app/data Docker volume mount was not found.'
    }
    $volumeName = ($dataMountLine -split '\s+')[0]

    return [pscustomobject]@{
        ContainerId = $containerId
        VolumeName = $volumeName
    }
}

function Get-LatestBackup {
    if (-not (Test-Path -LiteralPath $backupRoot -PathType Container)) {
        throw "No backup directory exists yet: $backupRoot"
    }
    $latest = Get-ChildItem -LiteralPath $backupRoot -File -Filter 'physiotherapy-*.db' |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
    if ($null -eq $latest) {
        throw "No database backup exists in: $backupRoot"
    }
    return $latest.FullName
}

function Resolve-BackupFile {
    param([string]$RequestedPath)
    if ([string]::IsNullOrWhiteSpace($RequestedPath)) {
        return Get-LatestBackup
    }
    return (Resolve-Path -LiteralPath $RequestedPath -ErrorAction Stop).Path
}

function Write-JsonFile {
    param([string]$Path, [object]$Value)
    $json = $Value | ConvertTo-Json -Depth 8
    $utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($Path, $json + [Environment]::NewLine, $utf8WithoutBom)
}

function New-DatabaseBackup {
    Write-Section 'ONLINE SQLITE BACKUP'
    Assert-File -Path $composeFile -Label 'Compose file'
    Assert-File -Path $environmentFile -Label 'Docker environment file'
    Assert-File -Path $localPython -Label 'Local Python'
    [void][System.IO.Directory]::CreateDirectory($backupRoot)

    $state = Get-BackendState
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $containerTemp = "/tmp/physiotherapy-$stamp.db"
    $backupPath = Join-Path $backupRoot "physiotherapy-$stamp.db"
    $manifestPath = "$backupPath.json"

    $backupCode = @"
import json
import os
import sqlite3

source_path = "$databasePath"
target_path = "$containerTemp"
source = sqlite3.connect("file:" + source_path + "?mode=ro", uri=True)
target = sqlite3.connect(target_path)
source.backup(target)
target.commit()
integrity = target.execute("pragma integrity_check").fetchone()[0]
target.close()
source.close()
print(json.dumps({"bytes": os.path.getsize(target_path), "integrity": integrity}, sort_keys=True))
"@

    try {
        $onlineResult = Invoke-ContainerPython -ContainerId $state.ContainerId -PythonCode $backupCode | ConvertFrom-Json
        if ($onlineResult.integrity -ne 'ok') {
            throw "Online backup integrity check failed: $($onlineResult.integrity)"
        }
        [void](Invoke-DockerCapture -DockerArgs @('cp', "$($state.ContainerId):$containerTemp", $backupPath))
    } finally {
        $cleanupCode = "import os; p='$containerTemp'; os.path.exists(p) and os.remove(p)"
        try {
            [void](Invoke-ContainerPython -ContainerId $state.ContainerId -PythonCode $cleanupCode)
        } catch {
            Write-Warning "Could not remove temporary container file: $containerTemp"
        }
    }

    $validation = Test-LocalDatabase -Path $backupPath
    $manifest = [ordered]@{
        schema_version = 1
        created_at = (Get-Date).ToString('o')
        source_container = $state.ContainerId
        source_volume = $state.VolumeName
        source_database = $databasePath
        backup_file = (Split-Path -Leaf $backupPath)
        bytes = $validation.bytes
        sha256 = $validation.sha256
        integrity = $validation.integrity
        tables = $validation.tables
        counts = $validation.counts
    }
    Write-JsonFile -Path $manifestPath -Value $manifest

    Write-Host "Backup: $backupPath" -ForegroundColor Green
    Write-Host "Manifest: $manifestPath"
    Write-Host "SHA-256: $($validation.sha256)"
    Write-Host 'BACKUP PASSED.' -ForegroundColor Green
    return $backupPath
}

function Invoke-RestoreDrill {
    param([string]$Path)
    Write-Section 'ISOLATED RESTORE DRILL'
    $resolvedBackup = Resolve-BackupFile -RequestedPath $Path
    $sourceValidation = Test-LocalDatabase -Path $resolvedBackup
    $manifestPath = "$resolvedBackup.json"

    if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
        $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($manifest.sha256 -ne $sourceValidation.sha256) {
            throw 'Backup SHA-256 does not match its manifest.'
        }
    } else {
        Write-Warning 'No manifest was found. Integrity will still be tested, but provenance cannot be confirmed.'
    }

    $suffix = (Get-Date -Format 'yyyyMMddHHmmss') + '-' + ([guid]::NewGuid().ToString('N').Substring(0, 8))
    $volumeName = "physiotherapy-client-restore-drill-$suffix"
    $containerName = "physiotherapy-restore-validator-$suffix"
    $volumeCreated = $false
    $containerCreated = $false
    $cleanupCompleted = $false

    try {
        [void](Invoke-DockerCapture -DockerArgs @('volume', 'create', $volumeName))
        $volumeCreated = $true
        [void](Invoke-DockerCapture -DockerArgs @(
            'create', '--pull=never', '--name', $containerName,
            '--mount', "type=volume,source=$volumeName,target=/restore",
            'python:3.11-slim', 'sleep', '300'
        ))
        $containerCreated = $true
        [void](Invoke-DockerCapture -DockerArgs @('start', $containerName))
        [void](Invoke-DockerCapture -DockerArgs @('cp', $resolvedBackup, "${containerName}:/restore/physiotherapy.db"))

        $validationCode = @'
import hashlib
import json
import os
import sqlite3

path = "/restore/physiotherapy.db"
connection = sqlite3.connect("file:" + path + "?mode=ro", uri=True)
tables = [row[0] for row in connection.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name")]
counts = {table: connection.execute('select count(*) from "' + table.replace('"', '""') + '"').fetchone()[0] for table in tables}
integrity = connection.execute("pragma integrity_check").fetchone()[0]
connection.close()
digest = hashlib.sha256()
with open(path, "rb") as stream:
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
print(json.dumps({"bytes": os.path.getsize(path), "counts": counts, "integrity": integrity, "sha256": digest.hexdigest(), "tables": tables}, sort_keys=True))
'@
        $restored = Invoke-ContainerPython -ContainerId $containerName -PythonCode $validationCode | ConvertFrom-Json
        if ($restored.integrity -ne 'ok') {
            throw "Restored database integrity check failed: $($restored.integrity)"
        }
        if ($restored.sha256 -ne $sourceValidation.sha256) {
            throw 'Restored database SHA-256 does not match the backup.'
        }

        Write-Host "Backup restored into temporary volume: $volumeName"
        Write-Host "Verified SHA-256: $($restored.sha256)"
        Write-Host "Verified tables: $($restored.tables.Count)"
    } finally {
        if ($containerCreated) {
            & $docker rm -f $containerName 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "Could not remove temporary container: $containerName"
            }
        }
        if ($volumeCreated) {
            & $docker volume rm $volumeName 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "Could not remove temporary volume: $volumeName"
            } else {
                $cleanupCompleted = $true
            }
        }
    }

    if (-not $cleanupCompleted) {
        throw 'Restore data passed validation, but temporary Docker cleanup did not complete.'
    }

    $drillPath = Join-Path $backupRoot ("restore-drill-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')
    $drillRecord = [ordered]@{
        schema_version = 1
        completed_at = (Get-Date).ToString('o')
        backup_file = (Split-Path -Leaf $resolvedBackup)
        bytes = $sourceValidation.bytes
        sha256 = $sourceValidation.sha256
        integrity = 'ok'
        tables = $sourceValidation.tables
        counts = $sourceValidation.counts
        isolated_volume_removed = $true
        validator_container_removed = $true
        live_volume_modified = $false
    }
    Write-JsonFile -Path $drillPath -Value $drillRecord
    Write-Host "Drill record: $drillPath"
    Write-Host 'RESTORE DRILL PASSED.' -ForegroundColor Green
    return $drillPath
}

function Show-BackupStatus {
    Write-Section 'BACKUP STATUS'
    if (-not (Test-Path -LiteralPath $backupRoot -PathType Container)) {
        Write-Host 'No backup directory exists yet.' -ForegroundColor Yellow
        return
    }
    $files = Get-ChildItem -LiteralPath $backupRoot -File | Sort-Object LastWriteTimeUtc -Descending
    if ($files.Count -eq 0) {
        Write-Host 'No backup files exist yet.' -ForegroundColor Yellow
        return
    }
    $files | Select-Object LastWriteTime, Length, Name | Format-Table -AutoSize
}

function Pause-Menu {
    [void](Read-Host 'Press ENTER to return to the menu')
}

function Show-Menu {
    while ($true) {
        Clear-Host
        Write-Host 'Physiotherapy Client - Backup and Restore Drill' -ForegroundColor Cyan
        Write-Host ''
        Write-Host '1  Create backup and run isolated restore drill (recommended)'
        Write-Host '2  Create database backup only'
        Write-Host '3  Verify latest backup in an isolated Docker volume'
        Write-Host '4  Show backup files and drill records'
        Write-Host '0  Exit'
        Write-Host ''
        $choice = Read-Host 'Choose'
        try {
            switch ($choice.Trim()) {
                '1' { $created = New-DatabaseBackup; [void](Invoke-RestoreDrill -Path $created); Pause-Menu }
                '2' { [void](New-DatabaseBackup); Pause-Menu }
                '3' { [void](Invoke-RestoreDrill -Path $BackupFile); Pause-Menu }
                '4' { Show-BackupStatus; Pause-Menu }
                '0' { return }
                default { Write-Host 'Invalid choice.' -ForegroundColor Yellow; Start-Sleep -Seconds 1 }
            }
        } catch {
            Write-Host ''
            Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "Log: $sessionLog" -ForegroundColor Yellow
            Pause-Menu
        }
    }
}

try {
    Assert-File -Path $docker -Label 'Docker CLI'
    Assert-File -Path $composeFile -Label 'Compose file'
    Assert-File -Path $environmentFile -Label 'Docker environment file'
    $env:Path = "$dockerBin;$previousPath"
    Start-Transcript -LiteralPath $sessionLog -Append | Out-Null
    $transcriptStarted = $true

    Ensure-DockerReady
    switch ($Action) {
        'full' {
            $created = New-DatabaseBackup
            [void](Invoke-RestoreDrill -Path $created)
        }
        'backup' { [void](New-DatabaseBackup) }
        'drill' { [void](Invoke-RestoreDrill -Path $BackupFile) }
        'status' { Show-BackupStatus }
        default { Show-Menu }
    }
} catch {
    Write-Error $_.Exception.Message
    exit 1
} finally {
    $env:Path = $previousPath
    if ($transcriptStarted) {
        Stop-Transcript | Out-Null
    }
}
