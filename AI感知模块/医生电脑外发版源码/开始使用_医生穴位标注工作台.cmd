@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0app\entry_bootstrap.ps1"
if errorlevel 1 (
    echo.
    echo Doctor annotation workbench failed. Please take a screenshot of this window.
    pause
)
endlocal
