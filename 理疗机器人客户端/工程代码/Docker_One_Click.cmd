@echo off
setlocal
cd /d "%~dp0"
title Physiotherapy Client - Docker Easy Menu
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0docker_easy_menu.ps1" %*
set "toolExit=%errorlevel%"
if not "%~1"=="" exit /b %toolExit%
if not "%toolExit%"=="0" (
  echo.
  echo The tool stopped with an error. Check the logs folder.
)
echo.
pause
endlocal
