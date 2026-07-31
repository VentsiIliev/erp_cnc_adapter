@echo off
REM ERP-CNC Adapter Watchdog
REM Checks if erp-cnc-adapter.exe is running; if not, starts it via the scheduled task.
REM Designed to be run by a scheduled task every 2 minutes.
REM Skips restart if an update or adapter startup preflight is in progress.

REM Find the adapter installation directory (look for erp-cnc-adapter.exe)
set "INSTALL_DIR=%~dp0.."
set "STARTUP_LOCK=%INSTALL_DIR%\logs\adapter-startup.lock"

REM Check for update lock file - if present, an update is in progress, do nothing
if exist "%INSTALL_DIR%\.update-lock" (
    exit /b 0
)

REM If the network preflight is already waiting to start the adapter, do not queue another launch.
if exist "%STARTUP_LOCK%" (
    exit /b 0
)

tasklist /FI "IMAGENAME eq erp-cnc-adapter.exe" 2>nul | find /I "erp-cnc-adapter.exe" >nul 2>&1
if %errorlevel% neq 0 (
    REM Process is not running - restart via scheduled task
    schtasks /Run /TN ERPCNCAdapter >nul 2>&1
)
