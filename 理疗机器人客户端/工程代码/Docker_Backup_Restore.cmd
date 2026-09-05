@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%docker_backup_restore.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo Backup or restore drill failed. Read the error above and the newest log in the logs folder.
    if "%~1"=="" pause
)
exit /b %EXIT_CODE%
